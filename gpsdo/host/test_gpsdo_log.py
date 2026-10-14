#!/usr/bin/env python3
from datetime import datetime, timezone
import io

from gpsdo_log import stamp, parse_telemetry, format_status, log_stream, OCXO_HZ, VDD


def test_utc_timestamp_and_stamp():
    dt = datetime(2026, 10, 14, 19, 0, 0, 123456, tzinfo=timezone.utc)
    stamped = stamp("019BFCC0 1F3 00989680 8000", dt)
    assert stamped == "2026-10-14T19:00:00.123456Z 019BFCC0 1F3 00989680 8000"


def test_parse_telemetry():
    assert parse_telemetry("019BFCC0 1F3 00989680 8000") == (10_000_000, 0x8000)
    assert parse_telemetry("2026-10-14T19:00:00.123456Z 019BFCC0 1F3 00989680 8000") == (10_000_000, 0x8000)
    assert parse_telemetry("019BFCC0 1F3") is None
    assert parse_telemetry("2026-10-14T19:00:00.123456Z 019BFCC0 1F3") is None
    assert parse_telemetry("019BFCC0 1F3 0098968G 8000") is None


def test_format_status():
    dt = datetime(2026, 10, 14, 19, 0, 0, tzinfo=timezone.utc)
    s = format_status(dt, 60, 0.5, 1.650, reconnects=0)
    assert "[19:00:00 UTC] 60 s  mean    +0.5 ppb  efc 1.650 V" in s
    assert "reconnects" not in s

    s_rec = format_status(dt, 45, -1.2, 1.642, reconnects=2)
    assert "[19:00:00 UTC] 45 s  mean    -1.2 ppb  efc 1.642 V  reconnects 2" in s_rec

    s_none = format_status(dt, 60, None, None, reconnects=0)
    assert "mean       -" in s_none


def test_log_stream_writes_file():
    lines = [
        "019BFCC0 1F3 00989680 8000\n",
        "019BFCC0 1F3 00989681 8004\n",
    ]
    out = io.StringIO()

    res = log_stream(lambda: list(lines), out, max_lines=2)
    assert res["total_lines"] == 2
    out_lines = out.getvalue().strip().split("\n")
    assert len(out_lines) == 2
    assert out_lines[0].endswith("019BFCC0 1F3 00989680 8000")
    assert out_lines[1].endswith("019BFCC0 1F3 00989681 8004")


def test_log_stream_minute_status_trigger():
    #generate 60 lines at 10 MHz (0 ppb) and 60 lines at 10 MHz + 1 count (100 ppb)
    lines = (
        ["019BFCC0 1F3 00989680 8000\n"] * 60 +
        ["019BFCC0 1F3 00989681 8000\n"] * 60
    )
    statuses = []

    curr_time = [1000.0]

    def mock_time():
        return curr_time[0]

    line_idx = [0]

    def mock_reader():
        while line_idx[0] < len(lines):
            line = lines[line_idx[0]]
            line_idx[0] += 1
            curr_time[0] += 1.0  #1 second per line
            yield line

    out = io.StringIO()
    res = log_stream(mock_reader, out, status_cb=statuses.append,
                     interval=60.0, max_lines=120, time_fn=mock_time)

    assert res["total_lines"] == 120
    assert len(statuses) == 2
    assert "mean    +0.0 ppb" in statuses[0]
    assert "mean  +100.0 ppb" in statuses[1]


def test_reconnect_survives_drop():
    #2 lines then a usb drop, 3 more then eof
    attempts = [0]

    def mock_reader():
        attempts[0] += 1
        if attempts[0] == 1:
            yield "019BFCC0 1F3 00989680 8000\n"
            yield "019BFCC0 1F3 00989681 8000\n"
            raise OSError("USB device disconnected")
        else:
            yield "019BFCC0 1F3 00989682 8000\n"
            yield "019BFCC0 1F3 00989683 8000\n"
            yield "019BFCC0 1F3 00989684 8000\n"

    out = io.StringIO()
    res = log_stream(mock_reader, out, max_lines=5, sleep_fn=lambda _: None)

    assert res["total_lines"] == 5
    assert res["reconnects"] >= 1
    assert attempts[0] >= 2
    out_lines = out.getvalue().strip().split("\n")
    assert len(out_lines) == 5
    assert out_lines[0].endswith("00989680 8000")
    assert out_lines[4].endswith("00989684 8000")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
