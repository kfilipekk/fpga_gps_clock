#!/usr/bin/env python3
#allan deviation of the ocxo locked and free running, with the board crystal
#from the locked run. takes two gpsdo_log.py captures, loop closed and open
#python3 ocxo_adev.py locked.log free.log [--skip 1800] [--png out.png]

import argparse

from timing import NOMINAL, allan_dev

OCXO_HZ = 10_000_000


def counts(lines):
    out = []
    for line in lines:
        f = line.split()
        if len(f) == 5:
            f = f[1:]
        if len(f) != 4:
            continue
        try:
            out.append((int(f[0], 16), int(f[2], 16)))
        except ValueError:
            continue
    return out


def analyse(locked, free):
    #counts spanning a pps gap are not one second
    def ocxo(rows):
        return [(o - OCXO_HZ) / OCXO_HZ for _, o in rows if abs(o - OCXO_HZ) < 50]
    #one continuous run, the two logs need not be back to back
    board = [(b - NOMINAL) / NOMINAL for b, _ in locked
             if abs(b - NOMINAL) < NOMINAL * 1e-3]
    #fewer than 8 blocks of tau leaves too few differences to trust
    def adev(y):
        return [(t, v) for t, v in allan_dev(y) if len(y) >= 8 * t]
    return {"board": adev(board), "free": adev(ocxo(free)),
            "locked": adev(ocxo(locked))}


def plot(r, h_locked, h_free, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, muted, grid = "#1a1a19", "#6b6a63", "#e4e3dc"
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    for name, key, col in (("board crystal", "board", muted),
                           ("ocxo free running", "free", "#eb6834"),
                           ("ocxo locked to gps, in loop", "locked", "#2a78d6")):
        t, s = zip(*r[key])
        ax.loglog(t, [v * 1e9 for v in s], "-o", color=col, lw=2, ms=5, label=name)
    t = [tau for tau, _ in r["board"]]
    #one count of phase quantisation, uniform, gives q / 2 tau
    ax.loglog(t, [50 / x for x in t], "--", color=muted, lw=1,
              label="ocxo counter resolution")
    ax.set_xlabel("averaging time τ (s)", color=ink)
    ax.set_ylabel("allan deviation (ppb)", color=ink)
    ax.set_title(f"ocxo against gps, {h_locked:.1f} h locked then {h_free:.1f} h free",
                 color=ink, loc="left")
    ax.grid(True, which="both", color=grid, lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=muted)
    ax.legend(frameon=False, labelcolor=ink)
    fig.tight_layout()
    fig.savefig(path)


def main():
    ap = argparse.ArgumentParser(description="ocxo allan deviation, locked vs free")
    ap.add_argument("locked")
    ap.add_argument("free")
    ap.add_argument("--skip", type=int, default=1800, help="pull-in seconds to drop")
    ap.add_argument("--png")
    a = ap.parse_args()
    with open(a.locked, errors="replace") as f:
        locked = counts(f)[a.skip:]
    with open(a.free, errors="replace") as f:
        free = counts(f)
    r = analyse(locked, free)
    print(f"locked {len(locked)} s, free {len(free)} s")
    board, free_d = dict(r["board"]), dict(r["free"])
    for tau, s in r["locked"]:
        free_s = f"{free_d[tau] * 1e9:7.3f}" if tau in free_d else "      -"
        print(f"{tau:6.0f} s  board {board[tau] * 1e9:7.2f} ppb  "
              f"free {free_s} ppb  locked {s * 1e9:7.3f} ppb")
    if a.png:
        plot(r, len(locked) / 3600, len(free) / 3600, a.png)


if __name__ == "__main__":
    main()
