#!/usr/bin/env python3
import math

from timing import NOMINAL, freq_error_ppb, allan_dev, fine_periods


def test_freq_error_zero():
    assert freq_error_ppb(NOMINAL) == 0.0


def test_freq_error_ppb():
    assert abs(freq_error_ppb(NOMINAL + 27) - 1000.0) < 1e-6


def test_allan_constant_is_zero():
    adev = allan_dev([0.0] * 64)
    assert adev and all(sigma == 0.0 for _tau, sigma in adev)


def test_allan_white_noise_averages_down():
    #white frequency noise falls as 1/sqrt(tau)
    import random
    random.seed(1)
    y = [random.gauss(0, 1e-9) for _ in range(4096)]
    adev = allan_dev(y)
    taus = dict(adev)
    assert taus[1.0] > taus[max(taus)]
    assert adev[0][0] == 1.0


def test_fine_periods_recover_sub_cycle():
    #pps 10.3 ns longer than a second, the taps have to find the fraction
    t, tap_ps = 1e12 / NOMINAL, 25.0
    lut = {k: k * tap_ps for k in range(2000)}
    rows, last = [], 0
    for k in range(8):
        edge = 1e6 + k * (1e12 + 10.3e3)
        n = math.ceil(edge / t)
        rows.append((n - last, round((n * t - edge) / tap_ps)))
        last = n
    q = fine_periods(rows[1:], lut)
    assert len(q) == 6
    for v in q:
        assert abs(v - (NOMINAL + 10.3e3 / t)) < 2 * tap_ps / t, v


def test_fine_periods_skip_dropouts():
    lut = {t: 25.0 * t for t in range(1000)}
    rows = [(NOMINAL, 500), (3 * NOMINAL, 500), (NOMINAL, 500), (NOMINAL, 500)]
    assert fine_periods(rows, lut) == [NOMINAL]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
