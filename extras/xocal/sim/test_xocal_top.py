import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from uart_util import recv_byte

CLK_NS = 37
SIG_NS = 290.7
PPS = 2500


async def pps_train(dut, n):
    for _ in range(n):
        await ClockCycles(dut.clk, PPS - 4)
        dut.pps.value = 1
        await ClockCycles(dut.clk, 4)
        dut.pps.value = 0


async def recv_line(dut):
    s = ""
    while not s.endswith("\n"):
        s += chr(await recv_byte(dut.clk, dut.uart_tx, 8))
    return s


def parse(s):
    assert s[0] == "X" and len(s) == 28, repr(s)
    return [int(f, 16) for f in s[1:].split()]


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_NS, "ns").start())
    cocotb.start_soon(Clock(dut.cc1101_data, SIG_NS, "ns").start())
    dut.pps.value = 0
    dut.cc1101_miso.value = 0
    await ClockCycles(dut.clk, 3)


@cocotb.test()
async def gps_gated_lines(dut):
    await start(dut)
    cocotb.start_soon(pps_train(dut, 20))
    await recv_line(dut)  #p may lag on the first
    for _ in range(3):
        m, c, p = parse(await recv_line(dut))
        assert p == PPS, p
        assert abs(c - PPS) < SIG_NS / CLK_NS + 2, c
        assert abs(c * CLK_NS / m - SIG_NS) < 2 * CLK_NS / m, (m, c)


@cocotb.test()
async def falls_back_without_pps(dut):
    await start(dut)
    await recv_line(dut)  #closes a window the previous test left open
    for _ in range(2):
        m, c, p = parse(await recv_line(dut))
        assert p == 0, p
        assert abs(c * CLK_NS / m - SIG_NS) < 2 * CLK_NS / m, (m, c)
    assert int(dut.led.value) & 0b10, "pps led lit with no pps"
