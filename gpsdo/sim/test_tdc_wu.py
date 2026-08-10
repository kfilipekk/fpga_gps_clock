import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

N = 32  #set in cocotb.mk
CHAINS = 4


@cocotb.test()
async def sums_all_chains(dut):
    #sim chains have no delay, the sum must be CHAINS*N
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    await ClockCycles(dut.clk, 3)

    for _ in range(3):
        dut.pps.value = 1
        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        assert int(dut.fine.value) == CHAINS * N, int(dut.fine.value)
        dut.pps.value = 0
        await ClockCycles(dut.clk, 5)
