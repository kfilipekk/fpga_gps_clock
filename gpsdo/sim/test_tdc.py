import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

N = 32  #set in cocotb.mk


@cocotb.test()
async def saturates_in_sim(dut):
    #sim chains have no delay, so every event reads full scale
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    await ClockCycles(dut.clk, 3)

    for _ in range(3):
        dut.pps.value = 1
        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        assert int(dut.fine.value) == N
        dut.pps.value = 0
        await ClockCycles(dut.clk, 5)
