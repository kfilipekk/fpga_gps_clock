import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

#scaled down in cocotb.mk
PULSE, ZERO, ONE, RESET = 5, 12, 25, 50


async def run(dut, level, width):
    dut.run_level.value = level
    dut.run_width.value = width
    dut.run_valid.value = 1
    await ClockCycles(dut.clk, 1)
    dut.run_valid.value = 0
    await ClockCycles(dut.clk, 2)


async def feed_frame(dut, bits):
    for b in bits:
        await run(dut, 1, PULSE)
        await run(dut, 0, ONE if b else ZERO)
    await run(dut, 1, PULSE)
    await run(dut, 0, RESET)


def frame_val(bits):
    return int("".join(str(b) for b in bits), 2)


@cocotb.test()
async def decodes_a_good_frame(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.run_valid.value = 0
    dut.sop.value = 0
    await ClockCycles(dut.clk, 5)

    bits = [1, 0, 1, 0, 0, 0, 1, 1] + [0, 1, 0, 0, 1, 0, 1, 1] + \
           [0, 0, 1, 1, 0, 1, 0, 1] + [1, 1, 1, 1, 1, 0, 1, 0] + [1, 1, 0, 1]

    got = []

    async def watch():
        for _ in range(4000):
            await ClockCycles(dut.clk, 1)
            if dut.frame_valid.value:
                got.append(int(dut.frame.value))

    cocotb.start_soon(watch())
    await feed_frame(dut, bits)
    await ClockCycles(dut.clk, 5)

    assert got == [frame_val(bits)], (got, frame_val(bits))


@cocotb.test()
async def rejects_a_bad_const_nibble(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.run_valid.value = 0
    dut.sop.value = 0
    await ClockCycles(dut.clk, 5)

    bits = [1] * 24 + [1, 1, 1, 0] + [0] * 8

    got = []

    async def watch():
        for _ in range(4000):
            await ClockCycles(dut.clk, 1)
            if dut.frame_valid.value:
                got.append(int(dut.frame.value))

    cocotb.start_soon(watch())
    await feed_frame(dut, bits)
    await ClockCycles(dut.clk, 5)

    assert got == [], got
