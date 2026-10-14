#!/usr/bin/env python3
#the ocxo against gps from the run lines: error each second, its mean over
#the last minute and the efc voltage. counts telescope, so the mean is good
#to 2 counts over the window, not 1 per second
#cat /dev/ttyUSB1 | python3 ocxo.py

import sys
from collections import deque

OCXO_HZ = 10_000_000
VDD = 3.3        #efc swing, the fpga io rail
WINDOW = 60


def parse(line):
    #PPPPPPPP FFF OOOOOOOO DDDD -> (ocxo count, efc word)
    f = line.split()
    if len(f) != 4:
        return None
    try:
        return int(f[2], 16), int(f[3], 16)
    except ValueError:
        return None


def ppb(count):
    return (count - OCXO_HZ) / OCXO_HZ * 1e9


def main():
    recent = deque(maxlen=WINDOW)
    for line in sys.stdin:
        r = parse(line)
        if r is None:
            continue
        count, word = r
        e = ppb(count)
        #a count over a pps gap spans several seconds
        if abs(e) > 1e5:
            recent.clear()
            print(f"{'gap':>9}          efc {word / 65536 * VDD:.3f} V", flush=True)
            continue
        recent.append(e)
        mean = sum(recent) / len(recent)
        print(f"{e:+9.0f} ppb  {mean:+8.1f} ppb over {len(recent):2d} s"
              f"  efc {word / 65536 * VDD:.3f} V", flush=True)


if __name__ == "__main__":
    main()
