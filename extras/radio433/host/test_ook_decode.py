#!/usr/bin/env python3
from ook_decode import parse, pwm_bits, nexus, classify


def test_parse_groups_packets():
    lines = [
        "@00000001 0000A000 010",
        "R1000064",
        "R0000032",
        "R10000C8",
        "@00000002 0000B000 020",
        "R1000064",
    ]
    pkts = list(parse(lines))
    assert len(pkts) == 2, pkts
    assert pkts[0]["sec"] == 1 and pkts[0]["sub"] == 0xA000
    assert pkts[0]["fine"] == 0x10
    assert pkts[0]["runs"] == [(1, 100), (0, 50), (1, 200)]
    assert pkts[1]["runs"] == [(1, 100)]


def test_parse_ignores_junk():
    lines = ["garbage", "R1000064", "", "@00000005 00000001 000", "R1000064"]
    pkts = list(parse(lines))
    assert len(pkts) == 1
    assert pkts[0]["sec"] == 5


def test_parse_dec_line():
    lines = [
        "@00000001 0000A000 010",
        "DB42DB42D",
        "R1000064",
    ]
    pkts = list(parse(lines))
    assert len(pkts) == 1
    assert pkts[0]["dec"] == "B42DB42D", pkts[0]


def test_parse_packet_without_dec():
    lines = ["@00000002 0000B000 020", "R1000064"]
    pkts = list(parse(lines))
    assert len(pkts) == 1
    assert "dec" not in pkts[0]


def test_pwm_short_long():
    runs = [(1, 100), (0, 50), (1, 300), (0, 50), (1, 100)]
    assert pwm_bits(runs, 27e6) == "010"


def test_pwm_needs_two_pulses():
    assert pwm_bits([(1, 100)], 27e6) == ""


def nexus_runs(id_, temp10, humi):
    t = temp10 & 0xFFF
    b = [id_, (0x8 << 4) | (t >> 8), t & 0xFF, 0xF0 | ((humi >> 4) & 0xF)]
    bits = [(x >> i) & 1 for x in b for i in range(7, -1, -1)]
    bits += [(humi >> i) & 1 for i in range(3, -1, -1)]
    runs = []
    for bit in bits:
        runs += [(1, 13500), (0, 54000 if bit else 27000)]
    return runs + [(1, 13500), (0, 108000)]


def test_nexus_decode():
    d = nexus(nexus_runs(0xA3, 215, 55))
    assert d["model"] == "ESP32-S3" and d["id"] == 0xA3
    assert abs(d["temp_c"] - 21.5) < 0.01 and d["humidity"] == 55


def test_nexus_real_device_labelled():
    d = nexus(nexus_runs(0x5C, 200, 60))
    assert d["model"] == "Nexus-TH" and d["id"] == 0x5C


def test_nexus_negative_temp():
    d = nexus(nexus_runs(0x5C, -45, 88))
    assert abs(d["temp_c"] + 4.5) < 0.01 and d["humidity"] == 88


def test_nexus_rejects_noise():
    assert nexus([(1, 13500), (0, 30000)] * 5) is None


def pwm_runs(bits, short=100, long_=300, gap=100):
    runs = []
    for b in bits:
        runs += [(1, long_ if b else short), (0, gap)]
    return runs


def test_classify_ppm():
    c = classify(nexus_runs(0xA3, 215, 55))
    assert c["coding"] == "ppm" and c["nbits"] == 36, c


def test_classify_pwm():
    bits = "10110010"
    c = classify(pwm_runs([int(b) for b in bits]))
    assert c["coding"] == "pwm" and c["bits"] == bits, c


def test_classify_checksum_sum8():
    data = 0x3C
    bits = f"{data:08b}{data:08b}"          #last byte is the sum
    c = classify(pwm_runs([int(b) for b in bits]))
    assert c["coding"] == "pwm" and c["checksum"] == "sum8", c


def test_classify_ppm_survives_outliers():
    #an outlier pulse must not turn ppm into manchester
    runs = nexus_runs(0x11, 200, 40)
    runs[0] = (1, 30000)
    c = classify(runs)
    assert c["coding"] == "ppm", c


def test_classify_rejects_short_noise():
    assert classify([(1, 100), (0, 50), (1, 120)]) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
