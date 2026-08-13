import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

N = 16  #set in cocotb.mk


@cocotb.test()
async def measures_the_interval(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.a.value = 0
    dut.b.value = 0
    await ClockCycles(dut.clk, 5)

    for gap in (100, 250, 40):
        dut.a.value = 1
        await RisingEdge(dut.clk)
        dut.a.value = 0
        await ClockCycles(dut.clk, gap - 1)
        dut.b.value = 1
        await RisingEdge(dut.clk)
        dut.b.value = 0

        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        assert int(dut.interval.value) == gap, (gap, int(dut.interval.value))
        assert int(dut.fine_a.value) == N
        assert int(dut.fine_b.value) == N
        await ClockCycles(dut.clk, 5)


@cocotb.test()
async def same_edge_on_both(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.a.value = 0
    dut.b.value = 0
    await ClockCycles(dut.clk, 5)

    for _ in range(3):
        dut.a.value = 1
        dut.b.value = 1
        await ClockCycles(dut.clk, 3)
        dut.a.value = 0
        dut.b.value = 0
        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        assert int(dut.interval.value) == 0, int(dut.interval.value)
        await ClockCycles(dut.clk, 5)
