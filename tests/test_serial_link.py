"""pty loopback tests for src/comm/serial_link.py (no hardware).

A FakeUno thread on the pty master speaks the same protocol as
firmware/serial_link/serial_link.ino. This tests the Pi side only: the real
firmware (watchdog, crc_err counting on the AVR) is checked on the Pi with
the bench positive controls.

Run from the repo root:
  python3 -m unittest discover -s tests -t . -v
"""

import os
import threading
import time
import unittest

from hw.limits import MOTOR_MAX_DUTY
from src.comm import serial_link as sl


class FakeUno(threading.Thread):
    def __init__(self, master_fd, send_ready=True, corrupt_ack_seqs=(), drop_ack_seqs=()):
        super().__init__(daemon=True)
        self.fd = master_fd
        self.send_ready = send_ready
        self.corrupt_ack_seqs = set(corrupt_ack_seqs)
        self.drop_ack_seqs = set(drop_ack_seqs)
        self.crc_err = 0
        self.fmt_err = 0
        self.received = []  # (seq, u_l, u_r) of valid commands
        self.stop = threading.Event()

    def _ack(self, seq):
        payload = f"A,{seq},{self.crc_err},{self.fmt_err},0,".encode()
        ck = sl.checksum(payload)
        if seq in self.corrupt_ack_seqs:
            ck ^= 0x01
        return payload + f"*{ck:02X}\n".encode()

    def _handle(self, line):
        star = line.rfind(b"*")
        if star < 0 or len(line) != star + 3:
            self.fmt_err += 1
            return
        if sl.checksum(line[:star]) != int(line[star + 1:], 16):
            self.crc_err += 1
            return
        parts = line[:star].decode().split(",")
        seq, u_l, u_r = int(parts[1]), int(parts[2]), int(parts[3])
        self.received.append((seq, u_l, u_r))
        if seq not in self.drop_ack_seqs:
            os.write(self.fd, self._ack(seq))

    def run(self):
        time.sleep(0.05)
        if self.send_ready:
            os.write(self.fd, b"boot-noise\nREADY,fw=fake,motor=0,wd_ms=50\n")
        buf = b""
        while not self.stop.is_set():
            try:
                chunk = os.read(self.fd, 256)
            except OSError:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line:
                    self._handle(line)


class SerialLinkPtyTest(unittest.TestCase):
    def start(self, **fake_kwargs):
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        fake = FakeUno(master, **fake_kwargs)
        fake.start()
        self.addCleanup(fake.stop.set)
        return fake, os.ttyname(slave)

    def drain(self, link, wait_s=0.2):
        events = []
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            events += link.poll()
            time.sleep(0.005)
        return events

    def test_normal_exchange(self):
        fake, port = self.start()
        link = sl.SerialLink(port, ready_timeout_s=2.0)
        self.addCleanup(link.close)
        self.assertEqual(link.stats.ready.get("fw"), "fake")
        self.assertEqual(link.stats.other_line, 1)  # "boot-noise" counted, not dropped
        for i in range(100):
            link.send(0.1, -0.1)
            link.poll()
            time.sleep(0.002)
        events = self.drain(link)
        s = link.stats
        # Preconditions (AGENTS.md 5-4): code under test really ran
        self.assertEqual(s.tx, 100)
        self.assertEqual(len(fake.received), 100)
        self.assertEqual(s.ack, 100)
        self.assertEqual((s.lost, s.bad_ack, s.unknown_seq), (0, 0, 0))
        self.assertTrue(all(e.rtt_s > 0 for e in events))
        self.assertEqual(fake.received[0], (0, 100, -100))

    def test_positive_control_corrupt_command_counted_by_uno(self):
        fake, port = self.start()
        link = sl.SerialLink(port, ready_timeout_s=2.0)
        self.addCleanup(link.close)
        link.send(0.0, 0.0, corrupt=True)
        link.send(0.0, 0.0)
        self.drain(link)
        self.assertEqual(fake.crc_err, 1)
        self.assertEqual(link.stats.remote.crc_err, 1)
        self.assertEqual(link.stats.ack, 1)
        self.assertEqual(link.stats.lost, 1)  # the corrupted command got no ack

    def test_positive_control_corrupt_ack_counted_by_pi(self):
        fake, port = self.start(corrupt_ack_seqs={1})
        link = sl.SerialLink(port, ready_timeout_s=2.0)
        self.addCleanup(link.close)
        for _ in range(3):
            link.send(0.0, 0.0)
        self.drain(link)
        self.assertEqual(link.stats.bad_ack, 1)
        self.assertEqual(link.stats.ack, 2)
        self.assertEqual(link.stats.lost, 1)

    def test_dropped_ack_is_lost_after_timeout(self):
        fake, port = self.start(drop_ack_seqs={0})
        link = sl.SerialLink(port, ready_timeout_s=2.0, ack_timeout_s=0.05)
        self.addCleanup(link.close)
        link.send(0.0, 0.0)
        self.drain(link, wait_s=0.03)
        self.assertEqual(link.stats.lost, 0)  # not yet expired
        self.drain(link, wait_s=0.1)
        self.assertEqual(link.stats.lost, 1)

    def test_ready_timeout_raises(self):
        fake, port = self.start(send_ready=False)
        t0 = time.monotonic()
        with self.assertRaises(sl.ReadyTimeout):
            sl.SerialLink(port, ready_timeout_s=0.3)
        self.assertLess(time.monotonic() - t0, 1.0)

    def test_clamp_to_motor_max_duty(self):
        fake, port = self.start()
        link = sl.SerialLink(port, ready_timeout_s=2.0)
        self.addCleanup(link.close)
        link.send(1.0, -1.0)
        self.drain(link)
        limit = sl.duty_to_permille(MOTOR_MAX_DUTY)
        self.assertEqual(fake.received[0][1:], (limit, -limit))
        self.assertEqual(link.stats.clipped, 2)


class CodecTest(unittest.TestCase):
    def test_round_trip_and_known_checksum(self):
        # Known value worked by hand: "M," gives 0x4D^0x2C = 0x61; each "0," adds 0x30^0x2C = 0x1C,
        # so 0x61^0x1C^0x1C^0x1C = 0x7D
        self.assertEqual(sl.encode_cmd(0, 0, 0), b"M,0,0,0,*7D\n")
        payload = b"A,7,1,2,3,"
        line = payload + f"*{sl.checksum(payload):02X}".encode()
        self.assertEqual(sl.parse_ack(line), sl.Ack(7, 1, 2, 3))

    def test_parse_ack_rejects(self):
        self.assertIsNone(sl.parse_ack(b"A,7,1,2,3,*00"))     # wrong checksum
        self.assertIsNone(sl.parse_ack(b"A,7,1,2,3,"))        # no checksum
        self.assertIsNone(sl.parse_ack(b"garbage"))

    def test_permille_sweep(self):
        # AGENTS.md 5-5: sweep the whole command range through the one conversion
        for i in range(-100, 101):
            d = i / 100
            self.assertEqual(sl.duty_to_permille(d), i * 10)


if __name__ == "__main__":
    unittest.main()
