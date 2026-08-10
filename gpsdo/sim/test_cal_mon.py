import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

N = 8  #set in cocotb.mk
DECIMATE = 4


@cocotb.test()
async def decimates_the_ring(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    got = 0
    for _ in range(3):
        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        assert int(dut.fine.value) == N, int(dut.fine.value)
        got += 1
    assert got == 3
