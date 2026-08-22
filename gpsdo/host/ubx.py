#!/usr/bin/env python3
#ubx-tim-tp parser

import struct

SYNC = b"\xb5\x62"
CLS, ID = 0x0D, 0x01
PAYLOAD = 16


def _checksum(body):
    #8 bit fletcher over class, id, length and payload
    a = b = 0
    for x in body:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return a, b


def frame(tow_ms=0, qerr_ps=0, week=0):
    payload = struct.pack("<IIiHBB", tow_ms, 0, qerr_ps, week, 0, 0)
    body = bytes([CLS, ID]) + struct.pack("<H", PAYLOAD) + payload
    return SYNC + body + bytes(_checksum(body))


def parse(data):
    #skips other messages and bad checksums
    i, n = 0, len(data)
    while True:
        i = data.find(SYNC, i)
        if i < 0 or i + 8 > n:
            return
        if data[i + 2] != CLS or data[i + 3] != ID:
            i += 2
            continue
        length = data[i + 4] | (data[i + 5] << 8)
        end = i + 6 + length
        if length != PAYLOAD or end + 2 > n:
            i += 2
            continue
        body = data[i + 2:end]
        if tuple(data[end:end + 2]) != _checksum(body):
            i += 2
            continue
        tow, _sub, qerr, week, _f, _r = struct.unpack("<IIiHBB", data[i + 6:end])
        yield {"tow_ms": tow, "qerr_ps": qerr, "week": week}
        i = end + 2


if __name__ == "__main__":
    import sys
    raw = sys.stdin.buffer.read()
    for r in parse(raw):
        print(f"tow {r['tow_ms']} ms  qErr {r['qerr_ps']:+d} ps  week {r['week']}")
