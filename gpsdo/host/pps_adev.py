#!/usr/bin/env python3
#allan deviation of the board crystal vs gps, count alone vs count + tdc
#python3 pps_adev.py capture.txt [--png out.png]

import argparse
import statistics

import tdc_cal
from timing import NOMINAL, allan_dev, fine_periods


def split(lines):
    pps, ring = [], []
    for line in lines:
        f = line.split()
        if len(f) != 2:
            continue
        try:
            p, tap = int(f[0], 16), int(f[1], 16)
        except ValueError:
            continue
        (pps if abs(p - NOMINAL) < NOMINAL * 1e-3 else ring).append((p, tap))
    return pps, ring


def analyse(pps, ring):
    cal = tdc_cal.characterise([t for _, t in ring], NOMINAL)
    lut = {r["tap"]: r["center"] for r in cal["rows"]}
    q = fine_periods(pps, lut)
    coarse = allan_dev([(p - NOMINAL) / NOMINAL for p, _ in pps])
    fine = allan_dev([(v - NOMINAL) / NOMINAL for v in q])
    return {"cal": cal, "coarse": coarse, "fine": fine,
            "ppm": (statistics.mean(q) - NOMINAL) / NOMINAL * 1e6,
            #per edge: a period difference is x2 - 2 x1 + x0
            "jitter_ns": statistics.pstdev(
                [b - a for a, b in zip(q, q[1:])]) / 6 ** 0.5 / NOMINAL * 1e9}


def plot(r, n, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid = "#1a1a19", "#6b6a63", "#e4e3dc"
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    for name, key, col in (("counter only, 37 ns steps", "coarse", "#eb6834"),
                           ("counter + tdc", "fine", "#2a78d6")):
        t, s = zip(*r[key])
        ax.loglog(t, [v * 1e9 for v in s], "-o", color=col, lw=2, ms=5,
                  label=name)
    t = [tau for tau, _ in r["fine"]]
    floor = 2 ** 0.5 * r["cal"]["sigma"] * 1e-3   #two edges, ppb at 1 s
    ax.loglog(t, [floor / x for x in t], "--", color=muted, lw=1,
              label="tdc single-shot floor")
    ax.set_xlabel("averaging time τ (s)", color=ink)
    ax.set_ylabel("allan deviation (ppb)", color=ink)
    ax.set_title(f"board crystal vs gps pps, {n} s, {r['ppm']:+.2f} ppm",
                 color=ink, loc="left")
    ax.grid(True, which="both", color=grid, lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=muted)
    ax.legend(frameon=False, labelcolor=ink)
    fig.tight_layout()
    fig.savefig(path)


def main():
    ap = argparse.ArgumentParser(description="pps allan deviation, coarse vs tdc")
    ap.add_argument("file")
    ap.add_argument("--png")
    a = ap.parse_args()
    with open(a.file, errors="replace") as f:
        pps, ring = split(f)
    r = analyse(pps, ring)
    print(f"pps {len(pps)} s, ring {len(ring)} samples, "
          f"tap median {r['cal']['median']:.1f} ps, sigma {r['cal']['sigma']:.0f} ps")
    print(f"crystal {r['ppm']:+.3f} ppm, pps edge jitter {r['jitter_ns']:.1f} ns rms")
    coarse = dict(r["coarse"])
    for tau, s in r["fine"]:
        print(f"{tau:6.0f} s  coarse {coarse[tau] * 1e9:7.2f} ppb  "
              f"fine {s * 1e9:7.2f} ppb")
    if a.png:
        plot(r, len(pps), a.png)


if __name__ == "__main__":
    main()
