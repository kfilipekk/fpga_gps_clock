import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from uart_util import recv_byte

DIV = 234
IDLE = 20000  #set in cocotb.mk
GLITCH_K = 6750
PWM_THRESH = 20250
SYNC = 0xD391
SYNC_LEN = 16
PAYLOAD_LEN = 32
SHORT, LONG, GAP = 12000, 26000, 8000


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


def bits(v, n):
    return [(v >> i) & 1 for i in range(n - 1, -1, -1)]


@cocotb.test()
async def decodes_hardware_size_payload(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.cc1101_data.value = 0
    await ClockCycles(dut.clk, 5)

    lines = []

    async def rx():
        while True:
            lines.append(await recv_line(dut))

    cocotb.start_soon(rx())

    stream = bits(SYNC, SYNC_LEN) + bits(0xB42DB42D, PAYLOAD_LEN)
    await hold(dut, 0, IDLE + 20)
    for b in stream:
        await hold(dut, 1, LONG if b else SHORT)
        await hold(dut, 0, GAP)
    await hold(dut, 0, IDLE + 20)

    nbytes = 23 + (2 + PAYLOAD_LEN // 4) + (2 * len(stream) - 1) * 9
    await ClockCycles(dut.clk, nbytes * 10 * DIV + 5000)

    assert len(lines) == 1 + 1 + (2 * len(stream) - 1), lines
    hdr = lines[0]
    assert hdr[0] == "@" and len(hdr) == 22, hdr
    assert lines[1] == "DB42DB42D", lines[1]
