import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

HALF = 10  #set in cocotb.mk


def half_bits(bits):
    out = []
    for b in bits:
        out += [0, 1] if b else [1, 0]
    return out


async def hold(dut, level, n):
    dut.sig.value = level
    await ClockCycles(dut.clk, n)


async def drive(dut, bits):
    halves = half_bits(bits)
    await hold(dut, 1 - halves[0], HALF * 5)  #idle is the complement of the first half bit
    for lvl in halves:
        await hold(dut, lvl, HALF)
    await hold(dut, halves[-1], HALF * 6)


async def collect(dut):
    got = []

    async def w():
        while True:
            await ClockCycles(dut.clk, 1)
            if dut.db_valid.value == 1:
                got.append(int(dut.db.value))

    cocotb.start_soon(w())
    return got


@cocotb.test()
async def recovers_the_bits(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.sig.value = 0
    await ClockCycles(dut.clk, 3)

    got = await collect(dut)
    bits = [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0]
    await drive(dut, bits)
    await ClockCycles(dut.clk, 3)

    assert got == bits, (got, bits)
