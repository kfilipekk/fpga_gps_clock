#!/usr/bin/env python3
from ocxo_adev import analyse, counts


def test_reads_raw_and_stamped_lines():
    rows = counts(["019BFCC0 4B0 00989680 8000",
                   "2026-10-15T00:00:00.000000Z 019BFCC1 4B0 00989681 8000",
                   "019BFCC0 4B0", "garbage"])
    assert rows == [(0x019BFCC0, 0x00989680), (0x019BFCC1, 0x00989681)]


def test_locked_beats_free_at_long_tau():
    #locked dithers one count, free drifts a count every 128 s
    locked = [(27_000_000, 10_000_000 + (i % 2)) for i in range(1024)]
    free = [(27_000_000, 10_000_000 + i // 128) for i in range(1024)]
    r = analyse(locked, free)
    assert dict(r["locked"])[256] < dict(r["free"])[256]


def test_gaps_left_out():
    rows = [(27_000_000, 10_000_000)] * 8 + [(270_000_000, 100_000_000)]
    r = analyse(rows, rows)
    assert all(v == 0 for _, v in r["locked"])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
