#!/usr/bin/env python3
#frequency error

import math

NOMINAL = 27_000_000


def freq_error_ppb(period):
    return (period - NOMINAL) / NOMINAL * 1e9


def allan_dev(y, rate=1.0):
    #non-overlapping, tau in powers of two
    n = len(y)
    out = []
    m = 1
    while m <= n // 3:
        k = n // m
        ybar = [sum(y[i * m:(i + 1) * m]) / m for i in range(k)]
        if len(ybar) > 1:
            s = sum((ybar[i + 1] - ybar[i]) ** 2 for i in range(len(ybar) - 1))
            out.append((m / rate, math.sqrt(s / (2 * (len(ybar) - 1)))))
        m *= 2
    return out


def load_lut(path):
    #tdc_cal.py --csv output, tap -> ps
    lut = {}
    with open(path) as f:
        next(f)
        for line in f:
            tap, _c, _w, _d, _i, center = line.split(",")
            lut[int(tap)] = float(center)
    return lut


def fine_periods(rows, lut, clk_hz=NOMINAL):
    #the edge sat lut[tap] ps before its clock
    out, prev = [], None
    for p, tap in rows:
        if tap not in lut or abs(p - clk_hz) > clk_hz * 1e-4:
            prev = None
            continue
        d = lut[tap] * clk_hz * 1e-12
        if prev is not None:
            out.append(p - d + prev)
        prev = d
    return out
