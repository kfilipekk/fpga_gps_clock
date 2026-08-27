import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

SHORT, LONG = 100, 200


async def run(dut, level, width):
    dut.run_level.value = level
    dut.run_width.value = width
    dut.run_valid.value = 1
    await ClockCycles(dut.clk, 1)
    dut.run_valid.value = 0
    await ClockCycles(dut.clk, 2)


async def collect(dut):
    got = []

    async def w():
        while True:
            await RisingEdge(dut.clk)
            await Timer(1, "ns")
            if dut.db_valid.value == 1:
                got.append(int(dut.db.value))

    cocotb.start_soon(w())
    return got


@cocotb.test()
async def adapts_to_the_pulse_widths(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.sop.value = 0
    dut.run_level.value = 0
    dut.run_width.value = 0
    dut.run_valid.value = 0
    await ClockCycles(dut.clk, 3)

    got = await collect(dut)

    await run(dut, 1, SHORT)
    await run(dut, 1, LONG)
    await run(dut, 1, SHORT)
    await run(dut, 1, LONG)
    await run(dut, 1, LONG)
    await run(dut, 1, SHORT)
    await ClockCycles(dut.clk, 3)

    assert got[2:] == [0, 1, 1, 0], got


@cocotb.test()
async def sop_resets_the_window(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.sop.value = 0
    dut.run_level.value = 0
    dut.run_width.value = 0
    dut.run_valid.value = 0
    await ClockCycles(dut.clk, 3)

    got = await collect(dut)

    await run(dut, 1, LONG)
    await run(dut, 1, SHORT)
    dut.sop.value = 1
    await ClockCycles(dut.clk, 1)
    dut.sop.value = 0
    await ClockCycles(dut.clk, 2)
    await run(dut, 1, SHORT)
    await ClockCycles(dut.clk, 3)

    assert got[-1] == 1, got
