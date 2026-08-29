#!/usr/bin/env python3
#decodes the radio433 uart stream into packets: @ header, D payload, runs
#cat /dev/ttyUSB1 | python3 ook_decode.py

import argparse
import sys

#our esp node uses the nexus format, its humidity field is a sound level
OUR_ID = 0xA3


def parse(lines):
    pkt = None
    for line in lines:
        line = line.strip()
        #the uart drops the odd byte, skip mangled lines
        try:
            if line.startswith("@"):
                if pkt:
                    yield pkt
                pkt = None
                f = line[1:].split()
                pkt = {"sec": int(f[0], 16), "sub": int(f[1], 16),
                       "fine": int(f[2], 16), "runs": []}
            elif line.startswith("D") and pkt is not None and len(line) >= 3:
                pkt["dec"] = line[1:]
            elif line.startswith("R") and pkt is not None and len(line) == 8:
                pkt["runs"].append((int(line[1]), int(line[2:8], 16)))
        except (ValueError, IndexError):
            continue
    if pkt:
        yield pkt


def pwm_bits(runs, clk_hz):
    #pulse width coding, split at the midpoint
    highs = [w for lvl, w in runs if lvl == 1]
    if len(highs) < 2:
        return ""
    mid = (min(highs) + max(highs)) / 2.0
    return "".join("1" if w > mid else "0" for w in highs)


def us(width, clk_hz):
    return width / clk_hz * 1e6


def _nexus_frame(bits):
    #9 nibbles: id id flags temp temp temp f humi humi
    if len(bits) < 36:
        return None
    b = [0, 0, 0, 0, 0]
    for k in range(36):
        b[k // 8] |= bits[k] << (7 - k % 8)
    if (b[3] & 0xF0) != 0xF0:
        return None
    t = ((b[1] & 0xF) << 8) | b[2]
    if t & 0x800:
        t -= 0x1000
    return {"model": "ESP32-S3" if b[0] == OUR_ID else "Nexus-TH",
            "id": b[0], "channel": ((b[1] >> 4) & 3) + 1,
            "battery": (b[1] >> 7) & 1, "temp_c": t / 10.0,
            "humidity": ((b[3] & 0xF) << 4) | (b[4] >> 4)}


def nexus(runs, clk_hz=27e6):
    #ppm: 500 us pulse then a 1 or 2 ms gap, a 3 ms+ gap ends the frame
    bits = []
    for j in range(len(runs) - 1):
        lvl, w = runs[j]
        glvl, gw = runs[j + 1]
        if lvl == 1 and glvl == 0 and 300 < us(w, clk_hz) < 800:
            gap = us(gw, clk_hz)
            if gap > 3000:
                d = _nexus_frame(bits)
                if d:
                    return d
                bits = []
            else:
                bits.append(1 if gap > 1500 else 0)
    return _nexus_frame(bits)


def _bimodal(xs):
    #ratio of the two cluster means, only if both hold >15%
    if not xs:
        return 0.0, 1.0
    th = (min(xs) + max(xs)) / 2.0
    low = [x for x in xs if x <= th]
    high = [x for x in xs if x > th]
    if not low or not high:
        return th, 1.0
    frac = min(len(low), len(high)) / len(xs)
    lm, hm = sum(low) / len(low), sum(high) / len(high)
    sep = hm / lm if lm > 0 else 1.0
    return th, (sep if frac > 0.15 else 1.0)


def _reset_threshold(lows):
    #the frame gap sits well above the data gaps, split at the biggest jump
    sl = sorted(set(round(g, 1) for g in lows))
    boundary = max(lows) + 1.0 if lows else 0.0
    for a, b in zip(sl, sl[1:]):
        if b > a * 1.8:
            boundary = (a + b) / 2.0
    return boundary


def _ppm_bits(runs, clk_hz, gap_th, reset_us):
    bits = []
    for j in range(len(runs) - 1):
        lvl, w = runs[j]
        glvl, gw = runs[j + 1]
        if lvl == 1 and glvl == 0:
            gap = us(gw, clk_hz)
            if gap >= reset_us:
                break
            bits.append(1 if gap > gap_th else 0)
    return "".join(str(b) for b in bits)


def _checksum(bits):
    #last byte as the sum or xor of the rest. noise almost never checks
    n = len(bits) // 8
    if n < 2:
        return None
    by = [int(bits[i * 8:(i + 1) * 8], 2) for i in range(n)]
    if (sum(by[:-1]) & 0xFF) == by[-1]:
        return "sum8"
    x = 0
    for b in by[:-1]:
        x ^= b
    if x == by[-1]:
        return "xor8"
    return None


def classify(runs, clk_hz=27e6):
    #coding, bits and checksum of a packet rtl_433 doesnt name
    highs = [us(w, clk_hz) for lvl, w in runs if lvl == 1]
    lows = [us(w, clk_hz) for lvl, w in runs if lvl == 0]
    if len(highs) < 4:
        return None
    reset_us = _reset_threshold(lows)
    data_lows = [g for g in lows if g < reset_us]
    h_th, h_sep = _bimodal(highs)
    l_th, l_sep = _bimodal(data_lows)

    coding, bits = "unknown", ""
    if l_sep > 1.6 and h_sep < 1.4:
        coding = "ppm"
        bits = _ppm_bits(runs, clk_hz, l_th, reset_us)
    elif h_sep > 1.6 and l_sep < 1.4:
        coding = "pwm"
        bits = "".join("1" if h > h_th else "0" for h in highs)
    elif h_sep > 1.6 and l_sep > 1.6:
        coding = "manchester"                #both widths bimodal
    return {"coding": coding, "nbits": len(bits), "bits": bits,
            "pulse_us": round(sum(highs) / len(highs)),
            "checksum": _checksum(bits)}


def main():
    ap = argparse.ArgumentParser(description="radio433 ook packet decode")
    ap.add_argument("file", nargs="?", default="-")
    ap.add_argument("--clk", type=float, default=27e6, help="Hz")
    ap.add_argument("--pulses", action="store_true", help="print run widths")
    a = ap.parse_args()

    f = sys.stdin if a.file == "-" else open(a.file)
    for i, pkt in enumerate(parse(f)):
        bits = pwm_bits(pkt["runs"], a.clk)
        span = us(sum(w for _, w in pkt["runs"]), a.clk)
        print(f"packet {i}: sec {pkt['sec']} sub {pkt['sub']} "
              f"fine {pkt['fine']} runs {len(pkt['runs'])} span {span:.0f}us")
        if "dec" in pkt:
            print(f"  fabric decode 0x{pkt['dec']} @ {pkt['sec']}s")
        n = nexus(pkt["runs"], a.clk)
        if n:
            rh = (f"sound {n['humidity']}" if n["model"] == "ESP32-S3"
                  else f"{n['humidity']}% rh")
            print(f"  {n['model']} id 0x{n['id']:02X} ch{n['channel']} "
                  f"batt{n['battery']} {n['temp_c']:.1f}C {rh}")
        c = classify(pkt["runs"], a.clk)
        if c and c["coding"] != "unknown":
            ck = c["checksum"] or "none"
            print(f"  classify: {c['coding']} pulse {c['pulse_us']}us "
                  f"{c['nbits']} bits checksum {ck}")
        if bits:
            val = int(bits, 2)
            print(f"  {len(bits)} bits  {bits}  0x{val:0{(len(bits)+3)//4}X}")
        if a.pulses:
            print("  " + " ".join(f"{lvl}:{us(w, a.clk):.0f}"
                                  for lvl, w in pkt["runs"]))


if __name__ == "__main__":
    main()
