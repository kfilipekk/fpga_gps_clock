from subghz import fingerprint

CLK = 27e6


def cyc(u):
    return round(u * CLK / 1e6)


def frame(bits, short=500, long=1000, gap=500):
    runs = []
    for b in bits:
        runs.append((1, cyc(long if b else short)))
        runs.append((0, cyc(gap)))
    return runs


def test_bimodal_decodes():
    bits = [0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0]
    fp = fingerprint(frame(bits))
    assert fp is not None, "bimodal frame not recognised"
    key, got = fp
    assert key == (500, 1000), key
    assert got == "".join(str(b) for b in bits), got
    print("ok  test_bimodal_decodes")


def test_noise_ignored():
    runs = [(1, cyc(600)) if i % 2 == 0 else (0, cyc(600)) for i in range(40)]
    assert fingerprint(runs) is None, "flat noise fingerprinted"
    print("ok  test_noise_ignored")


def test_too_few_pulses():
    assert fingerprint(frame([0, 1, 0])) is None
    print("ok  test_too_few_pulses")


if __name__ == "__main__":
    test_bimodal_decodes()
    test_noise_ignored()
    test_too_few_pulses()
    print("all passed")
