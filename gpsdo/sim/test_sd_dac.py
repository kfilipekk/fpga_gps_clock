import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

W = 8  #set in cocotb.mk


async def duty(dut, word, cycles=4000):
    dut.word.value = word
    await ClockCycles(dut.clk, 4)
    ones = 0
    for _ in range(cycles):
        await RisingEdge(dut.clk)
        ones += int(dut.pdm.value)
    return ones / cycles


@cocotb.test()
async def duty_tracks_word(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    full = 2**W
    for word in (0, full // 4, full // 2, 3 * full // 4, full - 1):
        d = await duty(dut, word)
        assert abs(d - word / full) < 0.02, (word, d)
