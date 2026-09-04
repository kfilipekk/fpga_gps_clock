#!/usr/bin/env python3
#flipper-style 433 monitor
#python3 subghz.py /dev/ttyUSB1
#python3 subghz.py capture.txt --once

import argparse
import json
import os
import sys
import time

from ook_decode import parse

CLK = 27e6
CAP_DIR = os.path.join(os.path.dirname(__file__), "captures")


def us(cycles):
    return cycles / CLK * 1e6


def fingerprint(runs):
    #(short_us, long_us, nbits, bits), or None for noise
    highs = [us(w) for lvl, w in runs if lvl == 1]
    if len(highs) < 12:
        return None
    lo = sorted(highs)
    short = lo[len(lo) // 5]
    long = lo[4 * len(lo) // 5]
    if long < short * 1.3:
        return None
    mid = (short + long) / 2
    bits = "".join("1" if h > mid else "0" for h in highs)
    #coarse bins so one device's jitter stays one row
    key = (round(short / 100) * 100, round(long / 250) * 250)
    return key, bits


class Device:
    def __init__(self, key):
        self.key = key
        self.count = 0
        self.last = 0.0
        self.bits = ""
        self.runs = []
        self.repeats = 0
        self.fixed = False


MIN_SEEN = 3


def redraw(devs):
    os.system("clear")
    print("  radio433 sub-ghz monitor   (ctrl-c to quit)\n")
    print("  #  short  long   seen  fixed  last bits")
    print("  " + "-" * 60)
    real = [d for d in devs.values() if d.count >= MIN_SEEN]
    for i, d in enumerate(sorted(real, key=lambda x: -x.count)):
        fixed = "yes" if d.fixed else "?"
        print(f"  {i:<2} {d.key[0]:>4}us {d.key[1]:>5}us {d.count:>5}"
              f"  {fixed:>4}   {d.bits[:28]}")
    noise = len(devs) - len(real)
    print(f"\n  {len(real)} devices (seen {MIN_SEEN}+ times), "
          f"{noise} one-off/noise. captures -> captures/")


def save(dev, name):
    os.makedirs(CAP_DIR, exist_ok=True)
    path = os.path.join(CAP_DIR, name + ".json")
    json.dump({"short_us": dev.key[0], "long_us": dev.key[1],
               "bits": dev.bits, "runs": dev.runs}, open(path, "w"), indent=2)
    return path


def main():
    ap = argparse.ArgumentParser(description="flipper-style 433 monitor")
    ap.add_argument("source", help="serial port or a recorded log file")
    ap.add_argument("--once", action="store_true", help="read a file to eof, no live redraw")
    ap.add_argument("--save-all", action="store_true", help="save every distinct signal")
    a = ap.parse_args()

    f = open(a.source, "r", errors="replace")
    devs = {}
    last_draw = 0.0
    saved = set()

    for pkt in parse(f):
        fp = fingerprint(pkt["runs"])
        if not fp:
            continue
        key, bits = fp
        d = devs.setdefault(key, Device(key))
        d.repeats = d.repeats + 1 if bits == d.bits else 0
        if d.repeats >= 2:      #same frame twice, fixed code
            d.fixed = True
        d.count += 1
        d.last = time.time()
        d.bits = bits
        d.runs = [[lvl, round(us(w))] for lvl, w in pkt["runs"]]
        if a.save_all and key not in saved:
            saved.add(key)
            save(d, f"dev_{key[0]}_{key[1]}")
        if not a.once and time.time() - last_draw > 0.3:
            redraw(devs)
            last_draw = time.time()

    if a.once:
        redraw(devs)
        for d in devs.values():
            if d.count >= MIN_SEEN:
                save(d, f"dev_{d.key[0]}_{d.key[1]}")


if __name__ == "__main__":
    main()
