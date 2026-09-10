#!/usr/bin/env python3
#synthetic capture: a clock 6.47 ppm slow, 3 ns of pps jitter

import math
import random

from pps_adev import analyse, split

TAP_PS = 30.0
T_PS = 1e12 / (27e6 * (1 - 6.47e-6))


def capture(secs=600):
    random.seed(2)
    lines, last = [], 0
    for k in range(secs + 1):
        edge = 5e5 + k * 1e12 + random.gauss(0, 3e3)
        n = math.ceil(edge / T_PS)
        if k:
            lines.append(f"{n - last:08X} {round((n * T_PS - edge) / TAP_PS):03X}")
        last = n
    taps = int(T_PS // TAP_PS)
    lines += [f"00000F00 {random.randrange(taps + 1):03X}" for _ in range(50000)]
    return lines


def test_split_on_period():
    pps, ring = split(capture(20) + ["garbage", "019BFCC0"])
    assert len(pps) == 20 and len(ring) == 50000


def test_tdc_beats_the_count():
    r = analyse(*split(capture()))
    coarse, fine = dict(r["coarse"]), dict(r["fine"])
    assert fine[1.0] < coarse[1.0] / 3, (fine[1.0], coarse[1.0])
    assert abs(r["ppm"] + 6.47) < 0.01, r["ppm"]
    assert 2.5 < r["jitter_ns"] < 3.5, r["jitter_ns"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
