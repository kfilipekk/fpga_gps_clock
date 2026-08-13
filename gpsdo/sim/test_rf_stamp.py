import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

N = 16  #set in cocotb.mk


async def edge(dut, sig):
    sig.value = 1
    await RisingEdge(dut.clk)
    sig.value = 0


@cocotb.test()
async def stamps_events_against_pps(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.evt.value = 0
    await ClockCycles(dut.clk, 5)

    for want_sec, gap in ((1, 60), (2, 200)):
        await edge(dut, dut.pps)
        await ClockCycles(dut.clk, gap - 1)
        await edge(dut, dut.evt)

        await RisingEdge(dut.valid)
        await Timer(1, "ns")
        assert int(dut.sec.value) == want_sec, int(dut.sec.value)
        assert int(dut.sub.value) == gap, int(dut.sub.value)
        assert int(dut.fine.value) == N
        await ClockCycles(dut.clk, 5)
