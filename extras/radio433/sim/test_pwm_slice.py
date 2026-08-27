import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

THRESH = 50  #set in cocotb.mk


async def run(dut, level, width):
    dut.run_level.value = level
    dut.run_width.value = width
    dut.run_valid.value = 1
    await ClockCycles(dut.clk, 1)
    dut.run_valid.value = 0
    await ClockCycles(dut.clk, 2)


@cocotb.test()
async def slices_short_and_long(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.sop.value = 0
    dut.run_level.value = 0
    dut.run_width.value = 0
    dut.run_valid.value = 0
    await ClockCycles(dut.clk, 3)

    got = []

    async def w():
        while True:
            await RisingEdge(dut.clk)
            await Timer(1, "ns")
            if dut.db_valid.value == 1:
                got.append(int(dut.db.value))

    cocotb.start_soon(w())

    await run(dut, 0, 999)
    await run(dut, 1, THRESH - 10)
    await run(dut, 1, THRESH + 10)
    await run(dut, 1, THRESH)
    await run(dut, 1, 1)
    await ClockCycles(dut.clk, 3)

    assert got == [0, 1, 0, 0], got
