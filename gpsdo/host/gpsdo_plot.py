#!/usr/bin/env python3
#plot lock-in, allan deviation and time error of an overnight gpsdo run
#python3 gpsdo_plot.py capture.log [--png out.png]

import argparse
from datetime import datetime
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timing import allan_dev

OCXO_HZ = 10_000_000
VDD = 3.3


def parse_log(lines):
    rows = []
    for line in lines:
        f = line.split()
        if not f:
            continue
        ts = None
        if len(f) in (5, 7):
            try:
                ts = datetime.fromisoformat(f[0].replace("Z", "+00:00"))
                fields = f[1:]
            except ValueError:
                fields = f
        else:
            fields = f

        if len(fields) not in (4, 6):
            continue

        try:
            p = int(fields[0], 16)
            tap = int(fields[1], 16)
            ocxo = int(fields[-2], 16)
            dac = int(fields[-1], 16)
            fine_b = int(fields[2], 16) if len(fields) == 6 else None
            interval = int(fields[3], 16) if len(fields) == 6 else None
        except ValueError:
            continue

        #reject pps dropouts/gaps spanning multi-second counts (>100 ppm)
        if abs(ocxo - OCXO_HZ) > 1000:
            continue

        rows.append({
            "timestamp": ts,
            "period": p,
            "tap": tap,
            "fine_b": fine_b,
            "interval": interval,
            "ocxo": ocxo,
            "dac": dac,
        })
    return rows


def analyse(rows):
    if not rows:
        return None

    t0 = rows[0]["timestamp"] if rows[0]["timestamp"] is not None else None
    t = []
    for i, r in enumerate(rows):
        if r["timestamp"] is not None and t0 is not None:
            t.append((r["timestamp"] - t0).total_seconds())
        else:
            t.append(float(i))

    freq_err_ppb = []
    voltage = []
    time_err_ns = []
    accum_cycles = 0

    y_frac = []
    for r in rows:
        o = r["ocxo"]
        w = r["dac"]
        e_ppb = (o - OCXO_HZ) / OCXO_HZ * 1e9
        freq_err_ppb.append(e_ppb)
        voltage.append(w / 65536.0 * VDD)
        y_frac.append((o - OCXO_HZ) / OCXO_HZ)

        accum_cycles += (o - OCXO_HZ)
        time_err_ns.append(accum_cycles * (1e9 / OCXO_HZ))

    adev = allan_dev(y_frac)
    res_limit = [(tau, (1e9 / OCXO_HZ) / tau) for tau, _ in adev]

    return {
        "n": len(rows),
        "t": t,
        "freq_err_ppb": freq_err_ppb,
        "voltage": voltage,
        "time_err_ns": time_err_ns,
        "adev": adev,
        "res_limit": res_limit,
        "mean_ppb": sum(freq_err_ppb) / len(freq_err_ppb),
        "std_ppb": statistics.pstdev(freq_err_ppb) if len(freq_err_ppb) > 1 else 0.0,
        "mean_v": sum(voltage) / len(voltage),
    }


def plot_lockin(r, path=None, ax=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    else:
        fig = ax.figure

    ink, muted, grid = "#1a1a19", "#6b6a63", "#e4e3dc"
    col_f, col_v = "#eb6834", "#2a78d6"

    t_max = max(r["t"]) if r["t"] else 1
    t_scale, unit = (1 / 3600.0, "h") if t_max > 7200 else (1.0, "s")
    t_plot = [x * t_scale for x in r["t"]]

    ax.plot(t_plot, r["freq_err_ppb"], color=col_f, lw=0.9, alpha=0.85, label="freq error")
    ax.set_ylabel("frequency error (ppb)", color=col_f)
    ax.tick_params(axis="y", colors=col_f)
    ax.tick_params(axis="x", colors=muted)
    ax.set_xlabel(f"elapsed time ({unit})", color=ink)
    ax.grid(True, color=grid, lw=0.6)

    ax2 = ax.twinx()
    ax2.plot(t_plot, r["voltage"], color=col_v, lw=1.2, label="tuning voltage")
    ax2.set_ylabel("tuning voltage (V)", color=col_v)
    ax2.tick_params(axis="y", colors=col_v)

    for side in ("top",):
        ax.spines[side].set_visible(False)
        ax2.spines[side].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax2.spines["left"].set_visible(False)

    ax.set_title(f"lock-in: frequency error and tuning voltage, {r['n']} s",
                 color=ink, loc="left")

    if standalone:
        fig.tight_layout()
        if path:
            fig.savefig(path)
    return fig


def plot_time_error(r, path=None, ax=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    else:
        fig = ax.figure

    ink, muted, grid = "#1a1a19", "#6b6a63", "#e4e3dc"
    col_time = "#2a78d6"

    t_max = max(r["t"]) if r["t"] else 1
    t_scale, unit = (1 / 3600.0, "h") if t_max > 7200 else (1.0, "s")
    t_plot = [x * t_scale for x in r["t"]]

    max_te = max(abs(x) for x in r["time_err_ns"]) if r["time_err_ns"] else 0
    te_scale, te_unit = (1e-3, "µs") if max_te > 5000 else (1.0, "ns")
    te_plot = [x * te_scale for x in r["time_err_ns"]]

    ax.plot(t_plot, te_plot, color=col_time, lw=1.2)
    ax.axhline(0, color=muted, lw=0.8, linestyle=":")
    ax.set_xlabel(f"elapsed time ({unit})", color=ink)
    ax.set_ylabel(f"time error ({te_unit})", color=ink)
    ax.set_title(f"time error against gps pps, end {te_plot[-1]:+.1f} {te_unit}",
                 color=ink, loc="left")
    ax.grid(True, color=grid, lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=muted)

    if standalone:
        fig.tight_layout()
        if path:
            fig.savefig(path)
    return fig


def plot_adev(r, path=None, ax=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    else:
        fig = ax.figure

    ink, muted, grid = "#1a1a19", "#6b6a63", "#e4e3dc"
    col_adev = "#2a78d6"

    tau, adev = zip(*r["adev"])
    ax.loglog(tau, [s * 1e9 for s in adev], "-o", color=col_adev, lw=2, ms=5,
              label="ocxo count")
    ax.loglog(tau, [100.0 / x for x in tau], "--", color=muted, lw=1.2,
              label="counter resolution limit (100 ns / τ)")
    ax.set_xlabel("averaging time τ (s)", color=ink)
    ax.set_ylabel("allan deviation (ppb)", color=ink)
    ax.set_title(f"allan deviation from ocxo counts, {r['n']} s",
                 color=ink, loc="left")
    ax.grid(True, which="both", color=grid, lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=muted)
    ax.legend(frameon=False, labelcolor=ink)

    if standalone:
        fig.tight_layout()
        if path:
            fig.savefig(path)
    return fig


def plot_all(r, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(8, 9.5), dpi=150)
    plot_lockin(r, ax=axes[0])
    plot_time_error(r, ax=axes[1])
    plot_adev(r, ax=axes[2])
    fig.tight_layout()
    fig.savefig(path)


def main():
    ap = argparse.ArgumentParser(description="plot gpsdo overnight run")
    ap.add_argument("file", help="log file from gpsdo_log.py or raw capture")
    ap.add_argument("--png", help="save combined summary figure to path")
    ap.add_argument("--lockin", help="save lock-in plot to path")
    ap.add_argument("--adev", help="save allan deviation plot to path")
    ap.add_argument("--time-error", help="save time-error plot to path")
    a = ap.parse_args()

    with open(a.file, errors="replace") as f:
        rows = parse_log(f)

    if not rows:
        print("no valid telemetry lines found", file=sys.stderr)
        sys.exit(1)

    r = analyse(rows)

    print(f"run: {r['n']} s ({r['n'] / 3600:.1f} h)")
    print(f"frequency error: mean {r['mean_ppb']:+.2f} ppb, stdev {r['std_ppb']:.2f} ppb")
    print(f"tuning voltage: mean {r['mean_v']:.3f} V")
    print(f"time error: final {r['time_err_ns'][-1]:+.1f} ns")
    if r["adev"]:
        print("allan deviation:")
        for (tau, s), (_, limit) in zip(r["adev"], r["res_limit"]):
            print(f"  {tau:6.0f} s   {s * 1e9:7.2f} ppb   (resolution limit {limit:7.2f} ppb)")

    if a.png:
        plot_all(r, a.png)
    if a.lockin:
        plot_lockin(r, a.lockin)
    if a.adev:
        plot_adev(r, a.adev)
    if a.time_error:
        plot_time_error(r, a.time_error)


if __name__ == "__main__":
    main()
