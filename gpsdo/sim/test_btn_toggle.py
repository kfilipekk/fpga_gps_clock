import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

HOLD = 4  #set in cocotb.mk


async def press(dut):
    dut.btn.value = 0
    await ClockCycles(dut.clk, HOLD + 6)
    dut.btn.value = 1
    await ClockCycles(dut.clk, HOLD + 6)
    await Timer(1, "ns")


@cocotb.test()
async def toggles_once_per_press(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.btn.value = 1
    await ClockCycles(dut.clk, HOLD * 3)
    await Timer(1, "ns")
    assert dut.state.value == 0

    await press(dut)
    assert dut.state.value == 1
    await press(dut)
    assert dut.state.value == 0
    await press(dut)
    assert dut.state.value == 1


@cocotb.test()
async def ignores_bounce(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.btn.value = 1
    await ClockCycles(dut.clk, HOLD * 3)
    await Timer(1, "ns")
    before = int(dut.state.value)

    for _ in range(8):
        dut.btn.value = 0
        await ClockCycles(dut.clk, 1)
        dut.btn.value = 1
        await ClockCycles(dut.clk, 1)

    await ClockCycles(dut.clk, HOLD * 3)
    await Timer(1, "ns")
    assert int(dut.state.value) == before
