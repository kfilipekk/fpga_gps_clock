#!/usr/bin/env python3
from ocxo import parse, ppb


def test_parses_run_lines_only():
    assert parse("019BFCC0 123 00989680 8000") == (10_000_000, 0x8000)
    assert parse("019BFCC0 123") is None
    assert parse("019BFCC0 123 0098968G 8000") is None


def test_one_count_is_100_ppb():
    assert ppb(10_000_000) == 0
    assert abs(ppb(10_000_001) - 100) < 1e-9


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
