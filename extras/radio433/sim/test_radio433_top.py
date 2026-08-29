import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from uart_util import recv_byte

DIV = 234
IDLE = 40  #set in cocotb.mk

#must match cocotb.mk
GLITCH_K = 5
PWM_THRESH = 20
SYNC = 0xA5
SYNC_LEN = 8
PAYLOAD_LEN = 8
SHORT, LONG, GAP = 10, 30, 10


async def recv_line(dut):
    chars = []
    while True:
        b = await recv_byte(dut.clk, dut.uart_tx, DIV)
        if b == 0x0A:
            return "".join(chars)
        chars.append(chr(b))


async def hold(dut, level, n):
    dut.cc1101_data.value = level
    await ClockCycles(dut.clk, n)


async def send_byte(dut, val):
    dut.uart_rx.value = 0
    await ClockCycles(dut.clk, DIV)
    for i in range(8):
        dut.uart_rx.value = (val >> i) & 1
        await ClockCycles(dut.clk, DIV)
    dut.uart_rx.value = 1
    await ClockCycles(dut.clk, DIV)


@cocotb.test()
async def dumps_a_packet(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.cc1101_data.value = 0
    dut.uart_rx.value = 1
    await ClockCycles(dut.clk, 5)

    lines = []

    async def rx():
        while True:
            lines.append(await recv_line(dut))

    cocotb.start_soon(rx())

    await hold(dut, 0, IDLE + 20)
    await hold(dut, 1, 30)
    await hold(dut, 0, 15)
    await hold(dut, 1, 25)
    await hold(dut, 0, IDLE + 20)

    await ClockCycles(dut.clk, 62 * 10 * DIV + 3000)

    assert len(lines) >= 4, lines
    hdr = lines[0]
    assert hdr[0] == "@" and hdr[9] == " " and hdr[18] == " ", hdr
    assert len(hdr) == 22, hdr
    int(hdr[1:9], 16); int(hdr[10:18], 16); int(hdr[19:22], 16)

    runs = [l for l in lines if l.startswith("R")]
    exp = [(1, 30), (0, 15), (1, 25)]
    assert len(runs) == 3, runs
    for (el, ew), line in zip(exp, runs):
        assert int(line[1]) == el, line
        w = int(line[2:8], 16)
        assert abs(w - ew) <= 2, (ew, w, line)


def bits(v, n):
    return [(v >> i) & 1 for i in range(n - 1, -1, -1)]


@cocotb.test()
async def pps_telemetry_line(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.cc1101_data.value = 0
    dut.uart_rx.value = 1
    await ClockCycles(dut.clk, 5)

    lines = []

    async def rx():
        while True:
            lines.append(await recv_line(dut))

    cocotb.start_soon(rx())

    for _ in range(2):
        await ClockCycles(dut.clk, 60)
        dut.pps.value = 1
        await ClockCycles(dut.clk, 5)
        dut.pps.value = 0

    await ClockCycles(dut.clk, 14 * 10 * DIV + 2000)

    pl = [l for l in lines if len(l) == 12 and l[8] == " "]
    assert pl, lines
    period = int(pl[0][0:8], 16)
    fine = int(pl[0][9:12], 16)
    assert period > 0, pl[0]
    assert 0 <= fine <= 16, pl[0]


@cocotb.test()
async def retransmits_on_command(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.cc1101_data.value = 0
    dut.uart_rx.value = 1
    dut.cc1101_miso.value = 0
    await ClockCycles(dut.clk, 5)

    lines = []

    async def rx():
        while True:
            lines.append(await recv_line(dut))

    cocotb.start_soon(rx())

    runs = [(1, 30), (0, 15), (1, 25)]
    await hold(dut, 0, IDLE + 20)
    for lvl, w in runs:
        await hold(dut, lvl, w)
    await hold(dut, 0, IDLE + 20)
    await ClockCycles(dut.clk, 62 * 10 * DIV + 3000)

    dut.cc1101_data.value = "z"
    seen = []

    async def sample(n):
        cur, w = None, 0
        for _ in range(n):
            v = str(dut.cc1101_data.value)
            if v in ("0", "1"):
                lvl = int(v)
                if lvl == cur:
                    w += 1
                else:
                    if cur is not None:
                        seen.append((cur, w))
                    cur, w = lvl, 1
            else:
                if cur is not None:
                    seen.append((cur, w))
                    cur, w = None, 0
            await ClockCycles(dut.clk, 1)
        if cur is not None:
            seen.append((cur, w))

    cocotb.start_soon(sample(20000))
    await send_byte(dut, ord("T"))
    await ClockCycles(dut.clk, 21000)

    #drop the one cycle skew blips at the last edge
    got = [r for r in seen if r[1] >= 3]
    assert got == runs, (got, runs)


@cocotb.test()
async def decodes_a_pwm_packet(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.cc1101_data.value = 0
    dut.uart_rx.value = 1
    await ClockCycles(dut.clk, 5)

    lines = []

    async def rx():
        while True:
            lines.append(await recv_line(dut))

    cocotb.start_soon(rx())

    stream = bits(SYNC, SYNC_LEN) + bits(0x3C, PAYLOAD_LEN)
    await hold(dut, 0, IDLE + 20)
    for i, b in enumerate(stream):
        await hold(dut, 1, LONG if b else SHORT)
        await hold(dut, 0, GAP)
        if i % 3 == 0:
            await hold(dut, 1, 2)
            await hold(dut, 0, 2)
    await hold(dut, 0, IDLE + 20)

    nbytes = 23 + (2 + PAYLOAD_LEN // 4) + (2 * len(stream) - 1) * 9
    await ClockCycles(dut.clk, nbytes * 10 * DIV + 5000)

    assert len(lines) == 1 + 1 + (2 * len(stream) - 1), lines
    hdr = lines[0]
    assert hdr[0] == "@" and hdr[9] == " " and hdr[18] == " ", hdr
    assert len(hdr) == 22, hdr
    assert lines[1] == "D3C", lines[1]

    runs = lines[2:]
    for j, line in enumerate(runs):
        lvl, w = int(line[1]), int(line[2:8], 16)
        if j % 2 == 0:
            b = stream[j // 2]
            assert lvl == 1, line
            assert abs(w - (LONG if b else SHORT)) <= 2, (b, w, line)
        else:
            k = j // 2
            gw = GAP + (4 if k % 3 == 0 else 0)
            assert lvl == 0, line
            assert abs(w - gw) <= 2, (w, gw, line)
