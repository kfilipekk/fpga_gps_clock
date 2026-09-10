#!/usr/bin/env python3
import math

from xocal import CARRIER, DIV, characterise, parse


def windows(xo_hz, clk_hz, secs, pps=True):
    #what xo_meter reports, window edge to window edge in whole clocks
    t_sig = DIV / xo_hz
    edges = [math.ceil(s / t_sig + 1e-9) * t_sig for s in range(secs + 1)]
    ticks = [math.floor(t * clk_hz) for t in edges]
    rows = []
    for i in range(secs):
        m = round((edges[i + 1] - edges[i]) / t_sig)
        p = round(clk_hz) + (i % 2) if pps else 0
        rows.append((m, ticks[i + 1] - ticks[i], p))
    return rows


def test_parse():
    assert parse("X00021100 019BFCC0 019BFC6B\n") == (0x21100, 0x19BFCC0, 0x19BFC6B)
    assert parse("@00000076 C45D445A 21D") is None
    assert parse("X0000000G 00000001 00000001") is None
    assert parse("X00000000 00000001 00000000") is None


def test_recovers_crystal_to_quantisation():
    xo = 26_000_000 * (1 + 12.3e-6)
    clk = 27_000_000.5
    r = characterise(windows(xo, clk, 60))
    assert r["gps"]
    err_hz = (r["xo_hz"] / xo - 1) * CARRIER
    assert abs(err_hz) < r["quant_hz"], (err_hz, r["quant_hz"])
    assert abs(r["xo_ppm"] - 12.3) < 0.01


def test_telescopes_with_run_length():
    xo, clk = 26_000_321.7, 27_000_000.5
    short = characterise(windows(xo, clk, 5))
    long = characterise(windows(xo, clk, 200))
    assert long["quant_hz"] < short["quant_hz"] / 30
    assert abs(long["xo_hz"] - xo) < abs(short["xo_hz"] - xo) + 1e-3


def test_corrected_word_lands_within_half_a_step():
    #the word steps in xo / 2^16, ~397 hz
    r = characterise(windows(26_000_000 * (1 - 20e-6), 27_000_000, 60))
    assert abs(r["carrier_err_hz"]) > 8000
    assert abs(r["word_err_hz"]) <= r["xo_hz"] / 2**17


def test_pps_dropout_spans_are_ignored():
    rows = windows(26e6, 27e6, 30)
    rows[10] = (rows[10][0], rows[10][1], 5 * 27_000_000)
    r = characterise(rows)
    assert r["quant_hz"] > characterise(windows(26e6, 27e6, 30))["quant_hz"]
    assert abs(r["clk_hz"] - 27e6) < 1
    assert abs(r["xo_ppm"]) < 0.05


def test_no_pps_is_flagged():
    r = characterise(windows(26e6, 27e6, 10, pps=False))
    assert not r["gps"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
