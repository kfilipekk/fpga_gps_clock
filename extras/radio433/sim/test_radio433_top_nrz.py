import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from uart_util import recv_byte

DIV = 234
BIT = 200  #set in cocotb.mk


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
async def decodes_nrz_packet(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.cc1101_data.value = 0
    await ClockCycles(dut.clk, 5)

    lines = []

    async def rx():
        while True:
            lines.append(await recv_line(dut))

    cocotb.start_soon(rx())

    stream = [1, 0] * 8 + bits(0xD391, 16) + bits(0xB42DB42D, 32)
    await hold(dut, 0, 1200)
    for b in stream:
        await hold(dut, b, BIT)
    await hold(dut, 0, 1200)

    await ClockCycles(dut.clk, 800 * 10 * DIV + 20000)

    ds = [ln for ln in lines if ln.startswith("D")]
    assert ds == ["DB42DB42D"], (ds, lines)
