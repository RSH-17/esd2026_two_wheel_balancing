#!/usr/bin/env python3
"""TEMP analysis for logs/experiments/2026-11-25-loop-jitter-cause.md (AGENTS.md 5-3).

Applies the preregistered rules to one --diag run of src/control/loop_bench.py.
Remove together with the --diag instrumentation once the cause is fixed.

Usage: python3 tools/analyze_jitter.py <run prefix> [<run prefix> ...]
"""

import bisect
import csv
import statistics
import sys

STALL_WRITE_US = 2000.0
LATE_DT_MS = 7.5
CHANCE_FACTOR = 3.0
FREQ_WINDOW_NS = 50_000_000   # +/- half the 10 Hz sample period
FREQ_BASELINE_MAX = 0.5       # above this, "near a change" covers too much of the run to discriminate


def load(prefix):
    rows = list(csv.DictReader(open(prefix + ".csv")))
    events = list(csv.DictReader(open(prefix + "-events.csv")))
    return rows, events


def overlap_rate(stalls, intervals, t_total_ns):
    """Fraction of stall windows overlapping any interval, and its chance level."""
    if not stalls or not intervals:
        return 0.0, 0.0, 0
    intervals = sorted(intervals)
    starts = [s for s, _ in intervals]
    hit = 0
    for w0, w1 in stalls:
        i = bisect.bisect_right(starts, w1)  # intervals starting before the window ends
        for s, e in intervals[max(0, i - 50):i]:
            if e >= w0:
                hit += 1
                break
    mean_w = statistics.mean(w1 - w0 for w0, w1 in stalls)
    busy = sum(e - s for s, e in intervals)
    chance = min(1.0, (busy + mean_w * len(intervals)) / t_total_ns)
    return hit / len(stalls), chance, hit


def analyse(prefix):
    rows, events = load(prefix)
    t0 = int(rows[0]["t_mono_ns"])
    t1 = int(rows[-1]["t_mono_ns"])
    t_total = t1 - t0
    stalls, ratios, stall_ticks = [], [], []
    for r in rows:
        w = float(r["write_us"])
        if w > STALL_WRITE_US:
            ws = int(r["write_t0_ns"])
            stalls.append((ws, ws + int(w * 1e3)))
            stall_ticks.append(int(r["tick"]))
            ratios.append(float(r["write_cpu_us"]) / w)
    late = [int(r["tick"]) for r in rows if r["dt_ms"] and float(r["dt_ms"]) > LATE_DT_MS]

    by_kind = {}
    for e in events:
        by_kind.setdefault(e["kind"], []).append(e)
    def inside(kind):  # only intervals while the control loop ran
        return [(int(e["t_start_ns"]), int(e["t_end_ns"])) for e in by_kind.get(kind, [])
                if t0 <= int(e["t_start_ns"]) <= t1]
    ros = inside("ros_cb")
    flush = inside("log_flush")
    freq = [(int(e["t_start_ns"]), e["value"]) for e in by_kind.get("cpu0_khz", [])]
    changes = sorted(freq[i][0] for i in range(1, len(freq)) if freq[i][1] != freq[i - 1][1])
    freq_vals = sorted({v for _, v in freq})

    ros_rate, ros_chance, ros_hit = overlap_rate(stalls, ros, t_total)
    fl_rate, fl_chance, fl_hit = overlap_rate(stalls, flush, t_total)
    def near(t):
        i = bisect.bisect_left(changes, t - FREQ_WINDOW_NS)
        return i < len(changes) and changes[i] <= t + FREQ_WINDOW_NS
    near_change = sum(1 for w0, _ in stalls if near(w0))
    all_near = sum(1 for r in rows if near(int(r["t_mono_ns"]))) / len(rows)
    ratio_med = statistics.median(ratios) if ratios else float("nan")
    outq_nz = sum(1 for r in rows if r["outq_before"] not in ("", "0", "-1"))

    print(f"== {prefix}")
    print(f"  ticks={len(rows)} duration={t_total / 1e9:.3f}s stall_ticks(write>{STALL_WRITE_US:.0f}us)={len(stalls)} "
          f"late_ticks(dt>{LATE_DT_MS}ms)={len(late)} first_late={late[:6]}")
    print(f"  write_cpu/write median over stalls={ratio_med:.3f}  ticks with outq_before>0: {outq_nz}")
    print(f"  ros_cb n={len(ros)} overlap={ros_rate:.3f} ({ros_hit}) chance={ros_chance:.3f} "
          f"ratio={ros_rate / ros_chance if ros_chance else float('nan'):.2f}")
    print(f"  log_flush n={len(flush)} overlap={fl_rate:.3f} ({fl_hit}) chance={fl_chance:.3f} "
          f"ratio={fl_rate / fl_chance if fl_chance else float('nan'):.2f}")
    print(f"  cpu0_khz values={freq_vals} changes={len(changes)} stalls within 50 ms of a change="
          f"{near_change}/{len(stalls)}  all ticks within 50 ms of a change={all_near:.3f}")
    return {
        "stalls": len(stalls), "late": len(late), "ratio_med": ratio_med,
        "ros": (ros_rate, ros_chance), "flush": (fl_rate, fl_chance),
        "near_change": near_change, "all_near": all_near, "has_ros": bool(ros),
    }


def main():
    res = {p: analyse(p) for p in sys.argv[1:]}
    if len(res) != 2:
        return 0
    (p_off, off), (p_on, on) = list(res.items())
    if off["stalls"] == 0 and on["stalls"] == 0:
        print("VERDICT  not reproduced (no stall ticks in either run)")
        return 0

    def above(rc):
        rate, chance = rc
        return chance > 0 and rate >= CHANCE_FACTOR * chance

    ga = on["has_ros"] and above(on["ros"]) and on["ratio_med"] < 0.5
    da = (min(off["stalls"], on["stalls"]) > 0
          and max(off["stalls"], on["stalls"]) <= 2 * min(off["stalls"], on["stalls"])
          and not any(above(r[k]) for r in (off, on) for k in ("ros", "flush") if r[k][1] > 0))
    total = off["stalls"] + on["stalls"]
    base = max(off["all_near"], on["all_near"])
    na_ok = base <= FREQ_BASELINE_MAX
    stall_frac = (off["near_change"] + on["near_change"]) / total if total else 0.0
    na = na_ok and stall_frac >= 0.5 and stall_frac >= 1.5 * base
    if not na_ok:
        print(f"NOTE   (na) cannot discriminate: {base:.3f} of all ticks are within 50 ms of a change")
    print(f"RULES  (ga) ROS contention={ga}  (da) write() itself={da}  (na) CPU freq change={na}")
    supported = [n for n, v in (("ga", ga), ("da", da), ("na", na)) if v]
    print("VERDICT " + (supported[0] if len(supported) == 1 else "undecided"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
