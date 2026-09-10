#!/usr/bin/env python3
#cc1101 crystal from the xocal lines: f_xo = 192 * m / c * p
#cat /dev/ttyUSB1 | python3 xocal.py

import math
import sys

XO_NOM = 26_000_000
DIV = 192                 #iocfg0 0x3f
CLK_NOM = 27_000_000
BOARD_PPM = -6.25         #radio433 readme, measured
CARRIER = 433_920_000
FREQ_WORD = 0x10B071


def parse(line):
    f = line.split()
    if len(f) != 3 or len(f[0]) != 9 or f[0][0] != "X":
        return None
    f[0] = f[0][1:]
    try:
        m, c, p = (int(x, 16) for x in f)
    except ValueError:
        return None
    return (m, c, p) if m and c else None


def characterise(rows):
    sm = sum(r[0] for r in rows)
    sc = sum(r[1] for r in rows)
    #a pps dropout makes one period span several seconds
    good = [abs(r[2] - CLK_NOM) < CLK_NOM * 1e-4 for r in rows]
    ps = [r[2] for r, g in zip(rows, good) if g]
    runs = sum(g and (i == 0 or not good[i - 1]) for i, g in enumerate(good))
    clk = sum(ps) / len(ps) if ps else CLK_NOM * (1 + BOARD_PPM * 1e-6)
    xo = DIV * sm / sc * clk
    word = round(CARRIER * 2**16 / xo)
    #a clock at each end of the span, and of each unbroken pps run
    quant = 2 / sc + (2 * math.sqrt(runs) / sum(ps) if ps else 0)
    return {
        "n": len(rows),
        "gps": bool(ps),
        "clk_hz": clk,
        "xo_hz": xo,
        "xo_ppm": (xo / XO_NOM - 1) * 1e6,
        "carrier_err_hz": FREQ_WORD * xo / 2**16 - CARRIER,
        "quant_hz": CARRIER * quant,
        "word": word,
        "word_err_hz": word * xo / 2**16 - CARRIER,
    }


def show(r):
    ref = "gps " if r["gps"] else "board"
    return (f"n {r['n']:4d} {ref}  xo {r['xo_hz']:.1f} Hz {r['xo_ppm']:+.3f} ppm  "
            f"433.92 off by {r['carrier_err_hz']:+.1f} Hz (+-{r['quant_hz']:.2f})  "
            f"word 0x{r['word']:06X} leaves {r['word_err_hz']:+.1f} Hz")


def main():
    rows = []
    for line in sys.stdin:
        row = parse(line)
        if row is None:
            continue
        rows.append(row)
        if len(rows) > 1:     #the first window starts mid second
            print(show(characterise(rows[1:])), flush=True)


if __name__ == "__main__":
    main()
