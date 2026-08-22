#!/usr/bin/env python3
from ubx import frame, parse


def test_roundtrip_signed_qerr():
    for q in (0, 500, -500, 2**31 - 1, -(2**31)):
        (r,) = list(parse(frame(qerr_ps=q)))
        assert r["qerr_ps"] == q, (q, r)


def test_carries_tow_and_week():
    (r,) = list(parse(frame(tow_ms=123456, qerr_ps=-42, week=2200)))
    assert r == {"tow_ms": 123456, "qerr_ps": -42, "week": 2200}


def test_finds_frame_in_noise():
    stream = b"\x00\xb5\x62junk" + frame(qerr_ps=17) + b"\xb5\x62\xff"
    got = [r["qerr_ps"] for r in parse(stream)]
    assert got == [17], got


def test_rejects_bad_checksum():
    bad = bytearray(frame(qerr_ps=99))
    bad[-1] ^= 0xFF
    assert list(parse(bytes(bad))) == []


def test_two_frames():
    stream = frame(qerr_ps=-3) + frame(qerr_ps=8)
    assert [r["qerr_ps"] for r in parse(stream)] == [-3, 8]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
