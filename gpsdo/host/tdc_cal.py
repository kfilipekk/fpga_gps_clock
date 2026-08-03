#!/usr/bin/env python3
#code density calibration: ring edges land evenly over the clock period
#python3 tdc_cal.py taps.txt --csv cal.csv

import argparse
import collections
import statistics
import sys


def read(f):
    out = []
    for line in f:
        parts = line.split()
        if parts:
            try:
                out.append(int(parts[-1], 16))
            except ValueError:
                pass
    return out


def characterise(values, clk_hz):
    period = 1e12 / clk_hz
    lo, hi = min(values), max(values)
    counts = collections.Counter(values)
    total = len(values)
    nbins = hi - lo + 1
    lsb = period / nbins

    rows, cum = [], 0.0
    for tap in range(lo, hi + 1):
        c = counts[tap]
        w = c / total * period
        dnl = w / lsb - 1.0
        center = cum + w / 2.0
        rows.append({"tap": tap, "count": c, "width": w,
                     "dnl": dnl, "center": center})
        cum += w

    inl = 0.0
    for r in rows:
        inl += r["dnl"]
        r["inl"] = inl

    seen = [r["width"] for r in rows if r["count"]]
    sigma = (sum((r["count"] / total) * r["width"] ** 2 / 12
                 for r in rows)) ** 0.5
    return {
        "rows": rows, "period": period, "lo": lo, "hi": hi,
        "nbins": nbins, "populated": len(seen), "total": total,
        "lsb": lsb, "median": statistics.median(seen),
        "dnl_max": max(r["dnl"] for r in rows),
        "dnl_min": min(r["dnl"] for r in rows),
        "inl_max": max(abs(r["inl"]) for r in rows),
        "sigma": sigma,
    }


def windows(values, n, clk_hz=27e6):
    #block by block, so tap drift as the die warms shows up
    for i in range(0, len(values) - n + 1, n):
        yield characterise(values[i:i + n], clk_hz)


def main():
    ap = argparse.ArgumentParser(description="tdc calibration + dnl/inl")
    ap.add_argument("file", nargs="?", default="-")
    ap.add_argument("--clk", type=float, default=27e6, help="Hz")
    ap.add_argument("--csv", help="write per tap table")
    ap.add_argument("--window", type=int,
                    help="rolling recal, block size, tracks thermal drift")
    a = ap.parse_args()

    f = sys.stdin if a.file == "-" else open(a.file)
    values = read(f)
    if not values:
        sys.exit("no samples")

    if a.window:
        print("block  codes  median_ps  span")
        for j, w in enumerate(windows(values, a.window, a.clk)):
            print(f"{j:5d}  {w['populated']:5d}  {w['median']:8.1f}  "
                  f"{w['lo']}..{w['hi']}")
        return

    s = characterise(values, a.clk)
    print(f"samples {s['total']}")
    print(f"codes   {s['lo']}..{s['hi']}, {s['populated']} of {s['nbins']} populated")
    print(f"period  {s['period']:.1f} ps")
    print(f"lsb     {s['lsb']:.1f} ps mean bin")
    print(f"tap     median {s['median']:.1f} ps")
    print(f"dnl     +{s['dnl_max']:.1f} / {s['dnl_min']:.1f} lsb, worst at the hops")
    print(f"inl     peak {s['inl_max']:.1f} lsb")
    print(f"sigma   {s['sigma']:.1f} ps single shot")
    print("widest taps, the segment hops:")
    for r in sorted(s["rows"], key=lambda r: -r["width"])[:5]:
        print(f"  tap {r['tap']:5d}  {r['width']:8.1f} ps  {r['count']} hits")

    if a.csv:
        with open(a.csv, "w") as out:
            out.write("tap,count,width_ps,dnl_lsb,inl_lsb,center_ps\n")
            for r in s["rows"]:
                out.write(f"{r['tap']},{r['count']},{r['width']:.3f},"
                          f"{r['dnl']:.4f},{r['inl']:.4f},{r['center']:.3f}\n")
        print(f"wrote {a.csv}")


if __name__ == "__main__":
    main()
