#!/usr/bin/env python3
#years to drift one second for each clock, from its allan deviation near
#1000 s. measured rows come from the 17.8 h run, the rest are typical values
#python3 compare.py out.png

import sys

YEAR = 365.25 * 86400

CLOCKS = [
    ("board crystal", 33e-9, "measured", "£15 board"),
    ("ocxo, free running", 1.4e-9, "measured", "£4"),
    ("this project, ocxo locked to gps", 0.32e-9, "measured, in loop", "£35 total"),
    ("commercial gpsdo or rubidium", 1e-12, "typical", "£100s to £1000s"),
    ("hydrogen maser", 2e-15, "typical", "£100,000s"),
]


def years(adev):
    return 1 / (adev * YEAR)


def rough(v):
    #typical values are order of magnitude, so say so
    if v >= 1e6:
        return f"~{v / 1e6:.0f} million years"
    return f"~{v / 1e3:.0f},000 years"


def plot(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid = "#1a1a19", "#6b6a63", "#e4e3dc"
    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=150)
    ax.set_axisbelow(True)
    names = [c[0] for c in CLOCKS][::-1]
    vals = [years(c[1]) for c in CLOCKS][::-1]
    cols = ["#2a78d6" if "project" in n else muted if "typical" in c[2] else "#eb6834"
            for n, c in zip(names, CLOCKS[::-1])]
    ax.barh(names, vals, color=cols, height=0.6)
    ax.set_xscale("log")
    for y, (v, c) in enumerate(zip(vals, CLOCKS[::-1])):
        label = rough(v) if "typical" in c[2] else f"{v:,.0f} years"
        label = "1 year" if label == "1 years" else label
        ax.text(v * 1.4, y, f"{label}   {c[3]}, {c[2]}", va="center",
                color=ink, fontsize=8)
    ax.set_xlim(0.3, 1e12)
    ax.set_xlabel("years to drift one second, at the rate it wanders over ~1000 s",
                  color=ink)
    ax.set_title("how steady is each clock", color=ink, loc="left")
    ax.grid(True, axis="x", which="major", color=grid, lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=muted)
    fig.tight_layout()
    fig.savefig(path)


if __name__ == "__main__":
    for name, adev, kind, cost in CLOCKS:
        print(f"{name:34s} {adev:8.1e}  {years(adev):12,.0f} years  {kind}")
    if len(sys.argv) > 1:
        plot(sys.argv[1])
