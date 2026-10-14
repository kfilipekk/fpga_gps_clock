#!/usr/bin/env python3
#overnight serial logger for the gpsdo: stamps every line with computer utc time,
#survives usb disconnects, writes to a file and prints a status each minute
#python3 gpsdo_log.py [/dev/ttyUSB1] [--out capture.log]

import argparse
from datetime import datetime, timezone
import os
import sys
import time

OCXO_HZ = 10_000_000
VDD = 3.3
DEFAULT_PORT = "/dev/ttyUSB1"
DEFAULT_BAUD = 115200


def stamp(line, now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return f"{ts} {line.strip()}"


def parse_telemetry(line):
    #raw: 4 or 6 tokens; stamped: 5 or 7 tokens
    f = line.split()
    if len(f) in (5, 7):
        f = f[1:]
    if len(f) not in (4, 6):
        return None
    try:
        return int(f[-2], 16), int(f[-1], 16)
    except ValueError:
        return None


def format_status(now, n_sec, mean_ppb, latest_efc, reconnects=0):
    t_str = now.strftime("%H:%M:%S UTC")
    mean_str = f"mean {mean_ppb:+7.1f} ppb" if mean_ppb is not None else "mean       -  "
    efc_str = f"efc {latest_efc:.3f} V" if latest_efc is not None else "efc     - "
    rec_str = f"  reconnects {reconnects}" if reconnects else ""
    return f"[{t_str}] {n_sec:2d} s  {mean_str}  {efc_str}{rec_str}"


def open_serial(port, baud=DEFAULT_BAUD):
    try:
        os.system(f"stty -F {port} {baud} raw -echo 2>/dev/null")
    except Exception:
        pass
    return open(port, "r", errors="replace")


def log_stream(reader_factory, out, status_cb=None, interval=60.0,
               max_lines=None, time_fn=time.time, sleep_fn=time.sleep):
    close_out = False
    if isinstance(out, str):
        out_f = open(out, "a", errors="replace")
        close_out = True
    else:
        out_f = out

    total_lines = 0
    period_lines = 0
    reconnects = 0
    recent_ppbs = []
    latest_efc = None
    last_status = time_fn()

    try:
        while max_lines is None or total_lines < max_lines:
            try:
                stream = reader_factory()
            except Exception:
                reconnects += 1
                sleep_fn(1.0)
                continue

            try:
                for line in stream:
                    if not line:
                        break
                    st = line.strip()
                    if not st:
                        continue
                    now_utc = datetime.now(timezone.utc)
                    stamped = stamp(st, now_utc)
                    out_f.write(stamped + "\n")
                    out_f.flush()

                    r = parse_telemetry(st)
                    if r is not None:
                        count, word = r
                        e = (count - OCXO_HZ) / OCXO_HZ * 1e9
                        if abs(e) <= 1e5:
                            recent_ppbs.append(e)
                        latest_efc = word / 65536.0 * VDD

                    total_lines += 1
                    period_lines += 1

                    now_t = time_fn()
                    if now_t - last_status >= interval:
                        mean = (sum(recent_ppbs) / len(recent_ppbs)) if recent_ppbs else None
                        msg = format_status(now_utc, period_lines, mean, latest_efc, reconnects)
                        if status_cb:
                            status_cb(msg)
                        else:
                            print(msg, flush=True)
                        last_status = now_t
                        period_lines = 0
                        recent_ppbs.clear()

                    if max_lines is not None and total_lines >= max_lines:
                        break
            except Exception:
                pass
            finally:
                if hasattr(stream, "close"):
                    try:
                        stream.close()
                    except Exception:
                        pass

            if max_lines is not None and total_lines >= max_lines:
                break

            reconnects += 1
            sleep_fn(1.0)
    finally:
        if close_out:
            out_f.close()

    return {"total_lines": total_lines, "reconnects": reconnects}


def main():
    ap = argparse.ArgumentParser(description="overnight gpsdo serial logger")
    ap.add_argument("port", nargs="?", default=DEFAULT_PORT,
                    help=f"serial device (default: {DEFAULT_PORT})")
    ap.add_argument("--out", "-o", default=None,
                    help="output log file (default: gpsdo_<date>.log)")
    ap.add_argument("--baud", "-b", type=int, default=DEFAULT_BAUD,
                    help=f"baud rate (default: {DEFAULT_BAUD})")
    ap.add_argument("--interval", type=float, default=60.0,
                    help="status reporting interval in seconds (default: 60)")
    a = ap.parse_args()

    if a.out is None:
        a.out = datetime.now(timezone.utc).strftime("gpsdo_%Y%m%d_%H%M%S.log")

    print(f"logging {a.port} to {a.out} at {a.baud} baud", flush=True)
    try:
        log_stream(lambda: open_serial(a.port, a.baud), a.out, interval=a.interval)
    except KeyboardInterrupt:
        print("\ninterrupted, closing log", flush=True)


if __name__ == "__main__":
    main()
