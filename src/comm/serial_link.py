"""Pi <-> Arduino Uno serial link for motor commands (AGENTS.md section 8-B).

Protocol (ASCII, one line each way, '\\n' terminated) — must match
firmware/serial_link/serial_link.ino:
  Uno -> Pi at boot : READY,fw=<name>,motor=<0|1>,wd_ms=<int>
  Pi  -> Uno        : M,<seq>,<u_l>,<u_r>,*<CK>
  Uno -> Pi         : A,<seq>,<crc_err>,<fmt_err>,<wd_trip>,*<CK>
seq is 0..65535 and wraps. u_l / u_r are signed duty in per-mille [-1000, 1000].
CK is the XOR of every byte before '*', as two upper-case hex digits.

The duty -> per-mille conversion lives only here (AGENTS.md section 5-5).
Commands are clamped to hw.limits.MOTOR_MAX_DUTY before they are encoded.

send() never blocks on a reply. poll() collects whatever acks have arrived and
matches them to the send time, so a control loop can call both every tick.
Every failure is counted in LinkStats; nothing is silently reused (section 8-B).

Quick check against a connected Uno (no motors are driven by stage-1 firmware):
  python3 -m src.comm.serial_link --count 200
"""

from __future__ import annotations

import glob
import time
from dataclasses import dataclass, field

import serial

from hw.limits import MOTOR_MAX_DUTY, clamp

BAUD = 115200                 # must equal BAUD in serial_link.ino
READY_TIMEOUT_S = 5.0         # Uno resets when the port opens; bootloader takes ~1-2 s
ACK_TIMEOUT_S = 0.1           # an ack older than this is counted as lost
PERMILLE = 1000
BY_ID_GLOB = "/dev/serial/by-id/usb-Arduino*"


class ReadyTimeout(RuntimeError):
    pass


def checksum(payload: bytes) -> int:
    ck = 0
    for b in payload:
        ck ^= b
    return ck


def duty_to_permille(duty: float) -> int:
    return int(round(duty * PERMILLE))


def encode_cmd(seq: int, u_l_pm: int, u_r_pm: int, corrupt: bool = False) -> bytes:
    payload = f"M,{seq},{u_l_pm},{u_r_pm},".encode("ascii")
    ck = checksum(payload)
    if corrupt:
        ck ^= 0xFF  # positive control: the Uno must count this in crc_err
    return payload + f"*{ck:02X}\n".encode("ascii")


@dataclass
class Ack:
    seq: int
    crc_err: int
    fmt_err: int
    wd_trip: int


def parse_ack(line: bytes) -> Ack | None:
    """Return the Ack, or None if the line is malformed or its checksum is wrong."""
    star = line.rfind(b"*")
    if star < 0 or len(line) != star + 3:
        return None
    try:
        want = int(line[star + 1:], 16)
    except ValueError:
        return None
    payload = line[:star]
    if checksum(payload) != want:
        return None
    parts = payload.decode("ascii", "replace").split(",")
    if len(parts) != 6 or parts[0] != "A" or parts[5] != "":
        return None
    try:
        seq, crc_err, fmt_err, wd_trip = (int(x) for x in parts[1:5])
    except ValueError:
        return None
    return Ack(seq, crc_err, fmt_err, wd_trip)


def parse_ready(line: bytes) -> dict[str, str] | None:
    text = line.decode("ascii", "replace")
    if not text.startswith("READY,"):
        return None
    info = {}
    for item in text[len("READY,"):].split(","):
        key, _, value = item.partition("=")
        info[key] = value
    return info


def find_port() -> str:
    ports = sorted(glob.glob(BY_ID_GLOB))
    if len(ports) != 1:
        raise RuntimeError(f"expected exactly one port matching {BY_ID_GLOB}, found {ports}")
    return ports[0]


@dataclass
class LinkStats:
    tx: int = 0               # commands sent
    ack: int = 0              # valid acks matched to a pending seq
    bad_ack: int = 0          # acks with a wrong checksum or format (Pi side)
    unknown_seq: int = 0      # valid acks whose seq was not pending
    other_line: int = 0       # lines that were neither READY nor an ack
    lost: int = 0             # commands with no ack within ack_timeout_s
    clipped: int = 0          # command values clipped by MOTOR_MAX_DUTY
    remote: Ack | None = None  # latest counters reported by the Uno
    ready: dict[str, str] = field(default_factory=dict)


@dataclass
class AckEvent:
    ack: Ack
    rtt_s: float
    t_send_ns: int  # time.monotonic_ns() when the command was written
    t_seen_ns: int  # time.monotonic_ns() at the start of the poll() that read the ack


class SerialLink:
    def __init__(self, port: str | None = None, baud: int = BAUD,
                 ready_timeout_s: float = READY_TIMEOUT_S,
                 ack_timeout_s: float = ACK_TIMEOUT_S):
        self.port = port or find_port()
        self.baud = baud
        self.ack_timeout_ns = int(ack_timeout_s * 1e9)
        self.stats = LinkStats()
        self._seq = 0
        self._pending: dict[int, int] = {}  # seq -> send time [ns, monotonic]
        self._rx = bytearray()
        self._ser = serial.Serial(self.port, self.baud, timeout=0)
        self._wait_ready(ready_timeout_s)

    def _wait_ready(self, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for line in self._read_lines():
                info = parse_ready(line)
                if info is not None:
                    self.stats.ready = info
                    return
                self.stats.other_line += 1
            time.sleep(0.005)
        self._ser.close()
        raise ReadyTimeout(f"no READY line from {self.port} within {timeout_s} s")

    def _read_lines(self) -> list[bytes]:
        n = self._ser.in_waiting
        if n:
            self._rx += self._ser.read(n)
        lines = []
        while True:
            i = self._rx.find(b"\n")
            if i < 0:
                return lines
            line = bytes(self._rx[:i]).rstrip(b"\r")
            del self._rx[:i + 1]
            if line:
                lines.append(line)

    def send(self, duty_l: float, duty_r: float, corrupt: bool = False) -> int:
        """Clamp, encode and send one command. Returns its seq. Never blocks on a reply."""
        u_l, c_l = clamp(duty_l, -MOTOR_MAX_DUTY, MOTOR_MAX_DUTY, "duty_l")
        u_r, c_r = clamp(duty_r, -MOTOR_MAX_DUTY, MOTOR_MAX_DUTY, "duty_r")
        self.stats.clipped += int(c_l) + int(c_r)
        seq = self._seq
        self._seq = (self._seq + 1) % 65536
        if seq in self._pending:  # wrapped onto an unanswered seq
            del self._pending[seq]
            self.stats.lost += 1
        self._ser.write(encode_cmd(seq, duty_to_permille(u_l), duty_to_permille(u_r), corrupt))
        self._pending[seq] = time.monotonic_ns()
        self.stats.tx += 1
        return seq

    def poll(self) -> list[AckEvent]:
        """Collect arrived acks, match them to send times, expire old pending seqs."""
        now = time.monotonic_ns()
        events = []
        for line in self._read_lines():
            ack = parse_ack(line)
            if ack is None:
                if line.startswith(b"A,"):
                    self.stats.bad_ack += 1
                else:
                    self.stats.other_line += 1
                continue
            self.stats.remote = ack
            t_send = self._pending.pop(ack.seq, None)
            if t_send is None:
                self.stats.unknown_seq += 1
                continue
            self.stats.ack += 1
            events.append(AckEvent(ack, (now - t_send) / 1e9, t_send, now))
        for seq, t_send in list(self._pending.items()):
            if now - t_send > self.ack_timeout_ns:
                del self._pending[seq]
                self.stats.lost += 1
        return events

    def close(self) -> None:
        self._ser.close()


def _main() -> None:
    import argparse
    import csv
    import os
    import statistics

    p = argparse.ArgumentParser(description="Send zero commands to the Uno and report RTT.")
    p.add_argument("--port", default=None)
    p.add_argument("--count", type=int, default=200)
    p.add_argument("--rate", type=float, default=200.0)
    # TEMP instrumentation (AGENTS.md 5-3): remove --mode/--trace in a separate commit
    # once the 205 ms RTT outlier of 2026-11-25 03:45 is explained.
    p.add_argument("--mode", choices=["tick", "tight"], default="tick",
                   help="tick: one poll per period; tight: busy-poll until the ack arrives")
    p.add_argument("--trace", default=None, help="prefix for per-ack and per-iteration CSVs")
    a = p.parse_args()

    link = SerialLink(a.port)
    print(f"port={link.port} baud={link.baud} mode={a.mode} rate={a.rate} ready={link.stats.ready}")
    period_ns = int(1e9 / a.rate)
    events: list[tuple[int, str, AckEvent]] = []   # (iter, phase, event)
    iters: list[tuple[int, int, int, int, int]] = []  # iter, t_start, t_sent, t_polled, n_ev
    t_next = time.monotonic_ns()
    for i in range(a.count):
        t0 = time.monotonic_ns()
        seq = link.send(0.0, 0.0)
        t1 = time.monotonic_ns()
        got = link.poll()
        if a.mode == "tight":
            deadline = t1 + link.ack_timeout_ns
            while not any(e.ack.seq == seq for e in got) and time.monotonic_ns() < deadline:
                got += link.poll()
        t2 = time.monotonic_ns()
        events += [(i, "loop", e) for e in got]
        iters.append((i, t0, t1, t2, len(got)))
        t_next += period_ns
        time.sleep(max(0, t_next - time.monotonic_ns()) / 1e9)
    time.sleep(ACK_TIMEOUT_S * 2)
    events += [(a.count, "drain", e) for e in link.poll()]
    link.close()

    s = link.stats
    print(f"tx={s.tx} ack={s.ack} lost={s.lost} bad_ack={s.bad_ack} "
          f"unknown_seq={s.unknown_seq} other_line={s.other_line} remote={s.remote}")

    def summary(label, rows):
        if rows:
            ms = [e.rtt_s * 1e3 for _, _, e in rows]
            print(f"rtt_ms[{label}] mean={statistics.mean(ms):.3f} sd={statistics.pstdev(ms):.3f} "
                  f"max={max(ms):.3f} min={min(ms):.3f} n={len(ms)}")
        else:
            print(f"rtt_ms[{label}] n=0")

    summary("all", events)
    summary("loop", [r for r in events if r[1] == "loop"])
    summary("drain", [r for r in events if r[1] == "drain"])
    worst = max(events, key=lambda r: r[2].rtt_s, default=None)
    if worst:
        print(f"worst: seq={worst[2].ack.seq} phase={worst[1]} iter={worst[0]} "
              f"rtt_ms={worst[2].rtt_s * 1e3:.3f}")
    dts = [(b[1] - a_[1]) / 1e6 for a_, b in zip(iters, iters[1:])]
    if dts:
        print(f"loop_dt_ms mean={statistics.mean(dts):.3f} max={max(dts):.3f} min={min(dts):.3f}")
        wr = [(it[2] - it[1]) / 1e6 for it in iters]
        print(f"write_ms mean={statistics.mean(wr):.3f} max={max(wr):.3f}")

    if a.trace:
        os.makedirs(os.path.dirname(a.trace) or ".", exist_ok=True)
        with open(a.trace + "-acks.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["seq", "phase", "iter", "t_send_ns", "t_seen_ns", "rtt_ms",
                        "crc_err", "fmt_err", "wd_trip"])
            for i, ph, e in events:
                w.writerow([e.ack.seq, ph, i, e.t_send_ns, e.t_seen_ns, f"{e.rtt_s * 1e3:.4f}",
                            e.ack.crc_err, e.ack.fmt_err, e.ack.wd_trip])
        with open(a.trace + "-iters.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["iter", "t_start_ns", "t_sent_ns", "t_polled_ns", "n_events"])
            w.writerows(iters)
        print(f"trace: {a.trace}-acks.csv {a.trace}-iters.csv")


if __name__ == "__main__":
    _main()
