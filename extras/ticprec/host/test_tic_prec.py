#!/usr/bin/env python3
#synthetic capture

import random

from tic_prec import precision, read, wave_union

T = 1e12 / 27e6


def chain(t_ps, hop_at, start):
    if t_ps < hop_at * 25:
        return start + int(t_ps // 25)
    if t_ps < hop_at * 25 + 5000:
        return start + hop_at
    return start + hop_at + 1 + int((t_ps - hop_at * 25 - 5000) // 25)


def capture(n=60000):
    random.seed(3)
    lines = []
    for _ in range(n):
        t = random.uniform(0, T)
        a = chain((t + 9012.5 + random.gauss(0, 20)) % T, 300, 100)
        b = chain((t + random.gauss(0, 20)) % T, 900, 0)
        lines.append(f"00000000 {a:03X} {b:03X}")
    return lines + ["00001D27 100 100", "junk"]


def test_read_keeps_zero_intervals():
    assert len(read(capture(10))) == 10


def test_precision_split():
    r = precision(read(capture()), 4095)
    assert r["saturated"] == 0
    assert 22 < r["clean_ps"] < 36, r["clean_ps"]     #sqrt(2) * 20 ps
    assert 1100 < r["hop_ps"] < 1800, r["hop_ps"]     #5 ns / sqrt(12)
    assert r["clean_n"] > r["hop_n"]


def test_wave_union_beats_either_chain():
    w = wave_union(read(capture()), 4095)
    assert w["a+b"]["lsb"] < 0.75 * w["b"]["lsb"]
    assert w["a+b"]["sigma"] < 0.5 * min(w["a"]["sigma"], w["b"]["sigma"])
    assert w["a+b"]["widest"] < w["b"]["widest"] / 3


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
