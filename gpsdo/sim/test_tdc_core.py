import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

N = 16  #set in cocotb.mk


async def event(dut, pattern):
    dut.trig.value = 1
    dut.taps.value = pattern
    await ClockCycles(dut.clk, 1)
    dut.taps.value = (1 << N) - 1
    await RisingEdge(dut.valid)
    await Timer(1, "ns")
    fine = int(dut.fine.value)
    dut.trig.value = 0
    dut.taps.value = 0
    await ClockCycles(dut.clk, 3)
    return fine


@cocotb.test()
async def counts_ones_with_bubbles(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.trig.value = 0
    dut.taps.value = 0
    await ClockCycles(dut.clk, 3)

    assert await event(dut, 0x00FF) == 8
    assert await event(dut, 0x0F0F) == 8
    assert await event(dut, 0xFFFF) == N
    assert await event(dut, 0x0001) == 1


@cocotb.test()
async def retriggers_never_read_a_stale_snapshot(dut):
    #sweep the spacing through the shift out window
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.trig.value = 0
    dut.taps.value = 0

    got = []

    async def monitor():
        while True:
            await RisingEdge(dut.valid)
            await Timer(1, "ns")
            got.append(int(dut.fine.value))

    cocotb.start_soon(monitor())

    for gap in range(N - 4, N + 9):
        for _ in range(6):
            dut.trig.value = 1
            dut.taps.value = 0x00FF
            await ClockCycles(dut.clk, 3)
            dut.trig.value = 0
            dut.taps.value = 0
            await ClockCycles(dut.clk, gap)

    bad = [v for v in got if v != 8]
    assert got and not bad, f"{len(bad)} of {len(got)} reads wrong: {bad[:8]}"


@cocotb.test()
async def no_retrigger_while_high(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.trig.value = 0
    dut.taps.value = 0
    await ClockCycles(dut.clk, 3)

    dut.trig.value = 1
    dut.taps.value = (1 << N) - 1
    await RisingEdge(dut.valid)
    for _ in range(3 * N):
        await RisingEdge(dut.clk)
        await Timer(1, "ns")
        assert dut.valid.value == 0
