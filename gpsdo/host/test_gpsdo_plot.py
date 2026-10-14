#!/usr/bin/env python3
from datetime import datetime, timezone
import os
import tempfile

from gpsdo_plot import parse_log, analyse, plot_lockin, plot_time_error, plot_adev, plot_all, OCXO_HZ


def test_parse_stamped_and_raw():
    lines = [
        "2026-10-14T19:00:00.000000Z 019BFCC0 1F3 00989680 8000\n",
        "2026-10-14T19:00:01.000000Z 019BFCC0 1F3 00989682 8010\n",
        "019BFCC0 1F3 0098967E 7FF0\n",  #raw line without timestamp
        "019BFCC0 1F3\n",                 #ring calibration line (ignored)
        "corrupted line\n",
        "2026-10-14T19:00:03.000000Z 019BFCC0 1F3 01000000 8000\n",  #huge gap (>100 ppm, ignored)
    ]
    rows = parse_log(lines)
    assert len(rows) == 3
    assert rows[0]["ocxo"] == 10_000_000
    assert rows[0]["dac"] == 0x8000
    assert rows[0]["timestamp"] == datetime(2026, 10, 14, 19, 0, 0, tzinfo=timezone.utc)
    assert rows[1]["ocxo"] == 10_000_002
    assert rows[2]["ocxo"] == 9_999_998
    assert rows[2]["timestamp"] is None


def test_frequency_error_and_voltage():
    lines = [
        "019BFCC0 1F3 00989680 8000\n",  #10,000,000 -> 0 ppb, 1.65 V
        "019BFCC0 1F3 00989685 4000\n",  #10,000,005 -> +500 ppb, 0.825 V
        "019BFCC0 1F3 0098967D C000\n",  #9,999,997 -> -300 ppb, 2.475 V
    ]
    r = analyse(parse_log(lines))
    assert len(r["freq_err_ppb"]) == 3
    assert abs(r["freq_err_ppb"][0] - 0.0) < 1e-6
    assert abs(r["freq_err_ppb"][1] - 500.0) < 1e-6
    assert abs(r["freq_err_ppb"][2] - (-300.0)) < 1e-6
    assert abs(r["voltage"][0] - 1.650) < 1e-3
    assert abs(r["voltage"][1] - 0.825) < 1e-3
    assert abs(r["voltage"][2] - 2.475) < 1e-3


def test_time_error_accumulation():
    #a cycle off nominal is 100 ns of time error
    lines = [
        "019BFCC0 1F3 00989681 8000\n",
        "019BFCC0 1F3 00989682 8000\n",
        "019BFCC0 1F3 00989680 8000\n",
        "019BFCC0 1F3 0098967F 8000\n",
    ]
    r = analyse(parse_log(lines))
    expected = [100.0, 300.0, 300.0, 200.0]
    for actual, exp in zip(r["time_err_ns"], expected):
        assert abs(actual - exp) < 1e-6, (actual, exp)


def test_allan_dev_and_resolution_limit():
    lines = ["019BFCC0 1F3 00989680 8000\n"] * 64
    r = analyse(parse_log(lines))
    assert len(r["adev"]) > 0
    for tau, dev in r["adev"]:
        assert dev == 0.0, (tau, dev)
    #counter limit is 100 ppb / tau
    for tau, limit in r["res_limit"]:
        assert abs(limit - (100.0 / tau)) < 1e-6, (tau, limit)


def test_synthetic_lockin_run():
    #starts 200 ppb slow and pulls in
    lines = []
    lines += ["019BFCC0 1F3 0098967E 7800\n"] * 20
    lines += ["019BFCC0 1F3 0098967F 7C00\n"] * 20
    lines += ["019BFCC0 1F3 00989680 8000\n"] * 40

    r = analyse(parse_log(lines))
    assert r["n"] == 80
    assert r["freq_err_ppb"][0] == -200.0
    assert r["freq_err_ppb"][-1] == 0.0
    assert r["voltage"][0] < r["voltage"][-1]
    assert r["time_err_ns"][19] < 0
    assert r["time_err_ns"][-1] == r["time_err_ns"][40]


def test_plot_rendering():
    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        print("skipping plot rendering test (matplotlib not installed in this python)")
        return

    lines = ["019BFCC0 1F3 00989680 8000\n"] * 32
    r = analyse(parse_log(lines))

    with tempfile.TemporaryDirectory() as tmp:
        p_all = os.path.join(tmp, "summary.png")
        p_lock = os.path.join(tmp, "lockin.png")
        p_adev = os.path.join(tmp, "adev.png")
        p_time = os.path.join(tmp, "time_error.png")

        plot_all(r, p_all)
        plot_lockin(r, path=p_lock)
        plot_adev(r, path=p_adev)
        plot_time_error(r, path=p_time)

        for p in (p_all, p_lock, p_adev, p_time):
            assert os.path.exists(p)
            assert os.path.getsize(p) > 1000
            with open(p, "rb") as f:
                header = f.read(8)
                assert header == b"\x89PNG\r\n\x1a\n", "invalid PNG header"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
