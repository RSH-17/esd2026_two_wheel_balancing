"""Stage-1 loop timing bench: control / log / ROS threads in one process.

Measures what the 200 Hz control loop actually gets on the Pi with the real
per-tick load (IMU burst read + serial send/poll + log enqueue), with ROS 2
off or on. Motors are not driven: commands are always 0 and the stage-1
firmware is built with MOTOR_ENABLE 0.

Threads (decision 2026-11-25 02:56, handoff):
  control : fixed-rate loop, never blocks on serial replies or disk
  log     : drains a queue into CSV (AGENTS.md 8-B: no SD writes in the loop)
  ros     : rclpy node, one parameter + a 50 Hz status publisher (--ros on)

Outputs (next to --out):
  <out>.csv        one row per tick, check with tools/check_log.py --rate <rate>
  <out>-acks.csv   one row per ack: seq, send_tick, seen_tick, rtt_ms
  <out>-meta.json  settings actually applied in this run (AGENTS.md 4-4)

Positive controls (AGENTS.md 4-4, 5-4):
  --inject-crc-at S   send one command with a wrong checksum at S seconds
                      -> Uno crc_err +1 and Pi lost +1 expected
  --pause-at S        control thread stops for --pause-ms at S seconds
                      -> Uno wd_trip +1 (if pause > wd_ms) and check_log VOID expected
  Row deletion is checked afterwards on a copy of the CSV with check_log.

Exit status 1 if a premise fails (no ticks, no acks, rows lost, ROS on but
nothing published), so a "PASS" can only come from a run that really ran.

Example:
  python3 -m src.control.loop_bench --duration 60 --ros off --out logs/raw/loop_bench/run1
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import queue
import statistics
import sys
import threading
import time

from hw.limits import MOTOR_MAX_DUTY
from src.comm import serial_link as sl

ROW_FIELDS = [
    "t", "tick", "dt_ms", "work_us",
    # AGENTS.md 8-B minimum fields; empty where stage 1 has no source yet
    "theta_deg", "gyro_dps", "wheel_l", "wheel_r", "u_l", "u_r", "vbat", "i2c_err",
    # raw IMU (no conversion until src/sensing/imu_calib.py exists)
    "ax", "ay", "az", "gx", "gy", "gz", "imu_us",
    # serial link
    "seq", "corrupt", "write_us", "n_ack", "ack_lag_max", "rtt_ms_max",
    "lost", "bad_ack", "unknown_seq", "remote_crc_err", "remote_fmt_err", "remote_wd_trip",
    # bench
    "paused", "q_depth",
    # TEMP diagnostics (--diag, AGENTS.md 5-3); empty without --diag
    "t_mono_ns", "cpu_us", "write_t0_ns", "write_cpu_us", "outq_before", "outq_after",
]
EVENT_FIELDS = ["kind", "t_start_ns", "t_end_ns", "value"]
ACK_FIELDS = ["seq", "send_tick", "seen_tick", "rtt_ms", "phase"]


def read_text(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def i2c_clock_hz(bus: int) -> int | None:
    try:
        with open(f"/sys/class/i2c-adapter/i2c-{bus}/of_node/clock-frequency", "rb") as f:
            return int.from_bytes(f.read(4), "big")
    except OSError:
        return None


class LogThread(threading.Thread):
    def __init__(self, path: str, fields: list[str]):
        super().__init__(name="log", daemon=True)
        self.q: queue.Queue = queue.Queue()
        self.path = path
        self.fields = fields
        self.rows_written = 0
        self.events: list[tuple] = []  # ("log_flush", t0, t1, rows)

    def run(self):
        with open(self.path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(self.fields)
            while True:
                row = self.q.get()
                if row is None:
                    break
                w.writerow(row)
                self.rows_written += 1
                if self.rows_written % 200 == 0:
                    t0 = time.monotonic_ns()
                    f.flush()
                    self.events.append(("log_flush", t0, time.monotonic_ns(), self.rows_written))

    def stop(self):
        self.q.put(None)
        self.join()


class RosThread(threading.Thread):
    """Parameters + monitoring only; never touches the serial link."""

    def __init__(self, status: dict, rate_hz: float = 50.0):
        super().__init__(name="ros", daemon=True)
        self.status = status
        self.rate_hz = rate_hz
        self.published = 0
        self.events: list[tuple] = []  # ("ros_cb", t0, t1, n)
        self.ready = threading.Event()
        self.error: str | None = None
        self.rclpy_info = ""
        self._executor = None

    def run(self):
        try:
            import rclpy
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.node import Node
            from std_msgs.msg import Float64MultiArray

            rclpy.init()
            node = Node("loop_bench")
            node.declare_parameter("bench_gain", 0.0)  # exercises the parameter service only
            pub = node.create_publisher(Float64MultiArray, "loop_bench/status", 10)

            def on_timer():
                t0 = time.monotonic_ns()
                s = self.status
                pub.publish(Float64MultiArray(data=[float(s.get("tick", 0)),
                                                    float(s.get("dt_ms", 0.0)),
                                                    float(s.get("rtt_ms_max", 0.0))]))
                self.published += 1
                self.events.append(("ros_cb", t0, time.monotonic_ns(), self.published))

            node.create_timer(1.0 / self.rate_hz, on_timer)
            self.rclpy_info = f"rmw={rclpy.get_rmw_implementation_identifier()}"
            self._executor = SingleThreadedExecutor()
            self._executor.add_node(node)
            self.ready.set()
            try:
                self._executor.spin()
            finally:
                node.destroy_node()
                rclpy.try_shutdown()
        except Exception as e:  # reported as a failed premise, not swallowed
            self.error = repr(e)
            self.ready.set()

    def stop(self):
        if self._executor is not None:
            self._executor.shutdown()
        self.join(timeout=5)


class SamplerThread(threading.Thread):
    """TEMP diagnostics: 10 Hz samples of cpu0 frequency and 1-min load average."""

    def __init__(self, rate_hz: float = 10.0):
        super().__init__(name="sampler", daemon=True)
        self.period = 1.0 / rate_hz
        self.events: list[tuple] = []
        self.stop_ev = threading.Event()

    def run(self):
        while not self.stop_ev.is_set():
            t0 = time.monotonic_ns()
            freq = read_text("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
            load = (read_text("/proc/loadavg") or "").split(" ")[0]
            t1 = time.monotonic_ns()
            self.events.append(("cpu0_khz", t0, t1, freq))
            self.events.append(("loadavg1", t0, t1, load))
            self.stop_ev.wait(self.period)

    def stop(self):
        self.stop_ev.set()
        self.join()


class ControlThread(threading.Thread):
    def __init__(self, a, link: sl.SerialLink, imu, log: LogThread, ack_log: LogThread,
                 status: dict):
        super().__init__(name="control", daemon=True)
        self.a = a
        self.link = link
        self.imu = imu  # (bus, read_fn) or None
        self.log = log
        self.ack_log = ack_log
        self.status = status
        self.ticks = 0
        self.overruns = 0
        self.i2c_err = 0
        self.dts_ms: list[float] = []
        self.work_us: list[float] = []
        self.send_tick: dict[int, int] = {}
        self.injected = 0
        self.paused = 0

    def run(self):
        a = self.a
        period_ns = int(1e9 / a.rate)
        n_ticks = int(round(a.duration * a.rate))
        inject_tick = None if a.inject_crc_at is None else int(a.inject_crc_at * a.rate)
        pause_tick = None if a.pause_at is None else int(a.pause_at * a.rate)
        t0 = time.monotonic_ns()
        t_next = t0
        t_prev = None
        for tick in range(n_ticks):
            paused = 0
            if tick == pause_tick:
                time.sleep(a.pause_ms / 1e3)
                self.paused += 1
                paused = 1
                t_next = time.monotonic_ns()  # restart the schedule after the pause
            t_start = time.monotonic_ns()
            c_start = time.thread_time_ns()
            dt_ms = "" if t_prev is None else (t_start - t_prev) / 1e6
            t_prev = t_start

            imu_vals = ["", "", "", "", "", ""]
            imu_us = ""
            if self.imu is not None:
                bus, read_fn = self.imu
                ti = time.monotonic_ns()
                try:
                    s = read_fn(bus)
                    imu_vals = [s.ax, s.ay, s.az, s.gx, s.gy, s.gz]
                except OSError:
                    self.i2c_err += 1
                imu_us = (time.monotonic_ns() - ti) / 1e3

            corrupt = tick == inject_tick
            self.injected += int(corrupt)
            seq = self.link.send(0.0, 0.0, corrupt=corrupt)
            self.send_tick[seq] = tick
            events = self.link.poll()
            lags, rtts = [], []
            for e in events:
                st = self.send_tick.pop(e.ack.seq, None)
                lag = "" if st is None else tick - st
                if st is not None:
                    lags.append(lag)
                rtts.append(e.rtt_s * 1e3)
                self.ack_log.q.put([e.ack.seq, st, tick, f"{e.rtt_s * 1e3:.4f}", "loop"])

            st_ = self.link.stats
            r = st_.remote
            work_us = (time.monotonic_ns() - t_start) / 1e3
            row = [
                f"{(t_start - t0) / 1e9:.6f}", tick,
                "" if dt_ms == "" else f"{dt_ms:.4f}", f"{work_us:.1f}",
                "", "", "", "", 0, 0, "", self.i2c_err,
                *imu_vals, "" if imu_us == "" else f"{imu_us:.1f}",
                seq, int(corrupt), f"{self.link.last_write_ns / 1e3:.1f}", len(events),
                max(lags) if lags else "", f"{max(rtts):.4f}" if rtts else "",
                st_.lost, st_.bad_ack, st_.unknown_seq,
                r.crc_err if r else "", r.fmt_err if r else "", r.wd_trip if r else "",
                paused, self.log.q.qsize(),
            ]
            if a.diag:
                L = self.link
                row += [t_start, f"{(time.thread_time_ns() - c_start) / 1e3:.1f}", L.last_write_t0_ns,
                        f"{L.last_write_cpu_ns / 1e3:.1f}", L.last_outq_before, L.last_outq_after]
            else:
                row += ["", "", "", "", "", ""]
            self.log.q.put(row)
            if dt_ms != "":
                self.dts_ms.append(dt_ms)
            self.work_us.append(work_us)
            self.status.update(tick=tick, dt_ms=dt_ms or 0.0, rtt_ms_max=max(rtts) if rtts else 0.0)
            self.ticks += 1

            t_next += period_ns
            slack = t_next - time.monotonic_ns()
            if slack > 0:
                time.sleep(slack / 1e9)
            else:
                self.overruns += 1

        # Drain: keep polling so late acks are timed on arrival or counted lost.
        deadline = time.monotonic_ns() + 2 * self.link.ack_timeout_ns
        while self.link.pending and time.monotonic_ns() < deadline:
            for e in self.link.poll():
                st = self.send_tick.pop(e.ack.seq, None)
                self.ack_log.q.put([e.ack.seq, st, n_ticks, f"{e.rtt_s * 1e3:.4f}", "drain"])


def pct(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True, help="output prefix, e.g. logs/raw/loop_bench/run1")
    p.add_argument("--duration", type=float, default=60.0, help="seconds")
    p.add_argument("--rate", type=float, default=200.0, help="Hz")
    p.add_argument("--ros", choices=["off", "on"], required=True)
    p.add_argument("--imu", choices=["on", "off"], default="on")
    p.add_argument("--port", default=None)
    p.add_argument("--inject-crc-at", type=float, default=None, help="seconds")
    p.add_argument("--pause-at", type=float, default=None, help="seconds")
    p.add_argument("--pause-ms", type=float, default=100.0)
    p.add_argument("--switch-interval", type=float, default=None,
                   help="sys.setswitchinterval() in seconds (Python default 0.005); applied value goes to meta")
    p.add_argument("--diag", action="store_true",
                   help="TEMP: per-tick CPU/write/outq columns, ROS/log/sampler event CSV")
    a = p.parse_args()

    if a.switch_interval is not None:
        sys.setswitchinterval(a.switch_interval)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    started = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    status: dict = {}

    ros = None
    if a.ros == "on":
        ros = RosThread(status)
        ros.start()
        ros.ready.wait(timeout=10)
        if ros.error:
            print(f"FAIL  ROS thread did not start: {ros.error}")
            return 1

    imu = None
    imu_who = None
    bus_obj = None
    if a.imu == "on":
        from smbus2 import SMBus
        from src.sensing import mpu6050_raw as mpu
        bus_obj = SMBus(mpu.I2C_BUS)
        imu_who = mpu.check_who_am_i(bus_obj)
        if imu_who != mpu.WHO_AM_I_EXPECTED:
            print(f"FAIL  MPU-6050 WHO_AM_I 0x{imu_who:02X}")
            return 1
        mpu.wake_up(bus_obj)
        imu = (bus_obj, mpu.read_raw)

    link = sl.SerialLink(a.port, diag=a.diag)
    sampler = SamplerThread() if a.diag else None
    if sampler is not None:
        sampler.start()
    log = LogThread(a.out + ".csv", ROW_FIELDS)
    ack_log = LogThread(a.out + "-acks.csv", ACK_FIELDS)
    log.start()
    ack_log.start()
    ctrl = ControlThread(a, link, imu, log, ack_log, status)
    print(f"start {started} ros={a.ros} imu={a.imu} rate={a.rate} duration={a.duration} "
          f"ready={link.stats.ready}")
    ctrl.start()
    ctrl.join()
    link.close()
    log.stop()
    ack_log.stop()
    if ros is not None:
        ros.stop()
    if bus_obj is not None:
        bus_obj.close()
    if sampler is not None:
        sampler.stop()
    if a.diag:
        evs = log.events + (ros.events if ros else []) + sampler.events
        with open(a.out + "-events.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(EVENT_FIELDS)
            w.writerows(sorted(evs, key=lambda e: e[1]))

    s = link.stats
    dts = ctrl.dts_ms
    acks = list(csv.DictReader(open(a.out + "-acks.csv")))
    lag_counts: dict[str, int] = {}
    for r in acks:
        if r["phase"] == "loop" and r["send_tick"] != "":
            k = str(int(r["seen_tick"]) - int(r["send_tick"]))
            lag_counts[k] = lag_counts.get(k, 0) + 1
    summary = {
        "ticks": ctrl.ticks, "rows_written": log.rows_written, "overruns": ctrl.overruns,
        "dt_ms": {"mean": statistics.mean(dts), "sd": statistics.pstdev(dts),
                  "p99": pct(dts, 0.99), "max": max(dts), "min": min(dts)} if dts else None,
        "work_us": {"mean": statistics.mean(ctrl.work_us), "p99": pct(ctrl.work_us, 0.99),
                    "max": max(ctrl.work_us)} if ctrl.work_us else None,
        "link": {"tx": s.tx, "ack": s.ack, "lost": s.lost, "bad_ack": s.bad_ack,
                 "unknown_seq": s.unknown_seq, "other_line": s.other_line, "clipped": s.clipped,
                 "remote": vars(s.remote) if s.remote else None},
        "ack_lag_ticks": dict(sorted(lag_counts.items(), key=lambda kv: int(kv[0]))),
        "i2c_err": ctrl.i2c_err, "injected_crc": ctrl.injected, "pauses": ctrl.paused,
        "ros_published": ros.published if ros else None,
        "diag": a.diag,
    }
    meta = {
        "started": started, "args": vars(a), "argv": sys.argv,
        "applied": {
            "rate_hz": a.rate, "baud": link.baud, "port": link.port, "ready": s.ready,
            "ack_timeout_s": link.ack_timeout_ns / 1e9, "motor_max_duty": MOTOR_MAX_DUTY,
            "imu": a.imu, "imu_who_am_i": imu_who, "i2c_clock_hz": i2c_clock_hz(1),
            "ros": a.ros, "ros_info": ros.rclpy_info if ros else None,
            "python": platform.python_version(), "kernel": platform.release(),
            "switch_interval_s": sys.getswitchinterval(),
            "cpu_governor": read_text("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
            "cpu_temp_c_end": (int(read_text("/sys/class/thermal/thermal_zone0/temp") or 0) / 1e3),
            "vbat": None,  # not measured in stage 1 (no motor battery connected)
            "theta_deg": "not computed: src/sensing/imu_calib.py does not exist yet",
        },
        "summary": summary,
    }
    with open(a.out + "-meta.json", "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2))

    # Premise checks (AGENTS.md 5-4): fail loudly if the code under test did not really run
    problems = []
    if ctrl.ticks == 0:
        problems.append("no control ticks")
    if log.rows_written != ctrl.ticks:
        problems.append(f"rows_written {log.rows_written} != ticks {ctrl.ticks}")
    if s.tx == 0 or s.ack == 0:
        problems.append(f"link did not exchange (tx={s.tx}, ack={s.ack})")
    if a.imu == "on" and ctrl.i2c_err == ctrl.ticks:
        problems.append("every IMU read failed")
    if ros is not None and ros.published == 0:
        problems.append("ROS on but nothing published")
    if problems:
        for m in problems:
            print(f"FAIL  {m}")
        return 1
    print(f"done  {a.out}.csv  (now run: python3 tools/check_log.py {a.out}.csv --rate {a.rate:g})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
