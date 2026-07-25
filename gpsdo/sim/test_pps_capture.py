import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

PERIOD = 1000
W = 16  #narrowed in cocotb.mk so it wraps


async def drive_pps(dut):
    #offset so edges never line up with clk
    await Timer(3, "ns")
    while True:
        dut.pps.value = 1
        await ClockCycles(dut.clk, 30)
        dut.pps.value = 0
        await ClockCycles(dut.clk, PERIOD - 30)


@cocotb.test()
async def measures_period_across_wrap(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    await ClockCycles(dut.clk, 5)
    cocotb.start_soon(drive_pps(dut))

    await RisingEdge(dut.tick)
    for _ in range(PERIOD // 2):
        await RisingEdge(dut.clk)
        assert dut.valid.value == 0

    #crosses the 16 bit wrap several times
    for _ in range(70):
        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        assert int(dut.period.value) == PERIOD
