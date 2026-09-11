#!/usr/bin/env python3
#single-shot precision from the ticprec lines
#python3 tic_prec.py capture.txt [--png out.png]

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../gpsdo/host"))
import tdc_cal

CLK = 27e6
HOP_PS = 300      #wider bins are segment hops


def read(lines):
    rows = []
    for line in lines:
        f = line.split()
        if len(f) != 3 or len(f[0]) != 8:
            continue
        try:
            i, a, b = (int(x, 16) for x in f)
        except ValueError:
            continue
        if i == 0:        #nonzero means the two syncs split
            rows.append((a, b))
    return rows


def _sd(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def precision(rows, top_a):
    t = 1e12 / CLK
    ca = tdc_cal.characterise([a for a, _ in rows], CLK)
    cb = tdc_cal.characterise([b for _, b in rows], CLK)
    la = {r["tap"]: (r["center"], r["width"]) for r in ca["rows"]}
    lb = {r["tap"]: (r["center"], r["width"]) for r in cb["rows"]}
    live = [(a, b) for a, b in rows if a < top_a]
    d = sorted(la[a][0] - lb[b][0] for a, b in live)
    mid = d[len(d) // 2]
    out = {"clean": [], "hop": []}
    for a, b in live:
        x = (la[a][0] - lb[b][0] - mid + t / 2) % t - t / 2
        hop = la[a][1] >= HOP_PS or lb[b][1] >= HOP_PS
        out["hop" if hop else "clean"].append(x)
    return {
        "n": len(rows), "saturated": len(rows) - len(live),
        "clean_n": len(out["clean"]), "hop_n": len(out["hop"]),
        "clean_ps": _sd(out["clean"]), "hop_ps": _sd(out["hop"]),
        "clean": out["clean"], "hop": out["hop"],
        "tap_a": ca["median"], "tap_b": cb["median"],
    }


def wave_union(rows, top_a):
    #saturated edges drop out, so scale to the part of the period left
    live = [(a, b) for a, b in rows if a < top_a]
    clk = CLK * len(rows) / len(live)
    out = {}
    for name, vals in (("a", [a for a, _ in live]), ("b", [b for _, b in live]),
                       ("a+b", [a + b for a, b in live])):
        c = tdc_cal.characterise(vals, clk)
        out[name] = {"codes": c["populated"], "lsb": c["lsb"], "sigma": c["sigma"],
                     "widest": max(r["width"] for r in c["rows"])}
    return out


def plot(r, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted = "#1a1a19", "#6b6a63"
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), dpi=150)
    panels = (("clean", "#2a78d6", "both edges in ordinary taps", r["clean_ps"], "ps"),
              ("hop", "#eb6834", "an edge in a segment-hop bin", r["hop_ps"], "ns"))
    for ax, (key, col, title, sd, unit) in zip(axes, panels):
        scale = 1 if unit == "ps" else 1e-3
        vals = [v * scale for v in r[key]]
        m = sum(vals) / len(vals)
        ax.hist([v - m for v in vals], bins=60, color=col)
        ax.set_title(f"{title}\n{sd * scale:.{0 if unit == 'ps' else 1}f} {unit} rms, "
                     f"{100 * len(vals) / r['n']:.0f}% of edges", color=ink, fontsize=10)
        ax.set_xlabel(f"a - b about its mean ({unit})", color=ink)
        ax.set_yticks([])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=muted)
    fig.suptitle(f"one edge timed on two tdc chains, {r['n']:,} edges", color=ink)
    fig.tight_layout()
    fig.savefig(path)


def main():
    ap = argparse.ArgumentParser(description="tic single-shot precision")
    ap.add_argument("file")
    ap.add_argument("--top", type=int, default=1200, help="chain length N")
    ap.add_argument("--png")
    a = ap.parse_args()
    with open(a.file, errors="replace") as f:
        rows = read(f)
    r = precision(rows, a.top)
    n = r["n"]
    print(f"{n} edges, median tap a {r['tap_a']:.1f} ps b {r['tap_b']:.1f} ps")
    print(f"ordinary taps  {r['clean_n']:6d} ({100 * r['clean_n'] / n:.0f}%)  "
          f"pair {r['clean_ps']:.1f} ps rms, one channel {r['clean_ps'] / 2 ** 0.5:.1f}")
    print(f"a hop bin      {r['hop_n']:6d} ({100 * r['hop_n'] / n:.0f}%)  "
          f"pair {r['hop_ps']:.0f} ps rms")
    print(f"a saturated    {r['saturated']:6d} ({100 * r['saturated'] / n:.0f}%)")
    print("wave union, same edges:")
    for name, w in wave_union(rows, a.top).items():
        print(f"  {name:4s} {w['codes']:4d} codes  bin {w['lsb']:5.1f} ps  "
              f"sigma {w['sigma']:4.0f} ps  widest {w['widest']:5.0f} ps")
    if a.png:
        plot(r, a.png)


if __name__ == "__main__":
    main()
