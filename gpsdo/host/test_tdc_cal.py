#!/usr/bin/env python3
from tdc_cal import characterise, read, windows
import io

CLK = 27e6
PERIOD = 1e12 / CLK


def approx(a, b, tol=1e-6):
    return abs(a - b) < tol


def test_widths_sum_to_period():
    values = list(range(200)) * 50
    s = characterise(values, CLK)
    total = sum(r["width"] for r in s["rows"])
    assert approx(total, PERIOD, 1e-3), total


def test_uniform_is_flat():
    values = list(range(200)) * 50
    s = characterise(values, CLK)
    assert approx(s["dnl_max"], 0.0, 1e-9)
    assert approx(s["inl_max"], 0.0, 1e-9)


def test_wide_bin_shows_positive_dnl():
    #one tap ten times as likely, like a segment hop
    values = list(range(100)) * 10 + [50] * 90
    s = characterise(values, CLK)
    fat = next(r for r in s["rows"] if r["tap"] == 50)
    assert fat["dnl"] > 5, fat["dnl"]
    assert s["dnl_max"] == fat["dnl"]


def test_windows_track_a_drift():
    #taps stretching as the die warms
    cold = list(range(100, 140)) * 20
    warm = list(range(100, 200)) * 8
    blocks = list(windows(cold + warm, 800))
    assert len(blocks) == 2
    assert blocks[1]["hi"] > blocks[0]["hi"]


def test_reader_takes_last_field():
    text = "01F\n019BFCC0 020\ngarbage\n\n0FF\n"
    assert read(io.StringIO(text)) == [0x1F, 0x20, 0xFF]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
