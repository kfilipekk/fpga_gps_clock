import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

CLK_NS = 37
SIG_NS = 290.7  #not a multiple of the clock
GATE = 3000


async def gates(dut):
    while True:
        await ClockCycles(dut.clk, GATE - 1)
        dut.gate.value = 1
        await RisingEdge(dut.clk)
        dut.gate.value = 0


@cocotb.test()
async def reciprocal_count_telescopes(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_NS, "ns").start())
    cocotb.start_soon(Clock(dut.sig, SIG_NS, "ns").start())
    dut.gate.value = 0
    await ClockCycles(dut.clk, 3)
    cocotb.start_soon(gates(dut))

    sm = sc = 0
    for i in range(12):
        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        m, c = int(dut.m.value), int(dut.c.value)
        assert abs(c - GATE) < SIG_NS / CLK_NS + 2, (m, c)
        assert abs(c * CLK_NS / m - SIG_NS) < 2 * CLK_NS / m, (m, c)
        if i:  #the first window starts at an arbitrary edge
            sm, sc = sm + m, sc + c
    assert abs(sc * CLK_NS / sm - SIG_NS) < 2 * CLK_NS / sm, (sm, sc)
