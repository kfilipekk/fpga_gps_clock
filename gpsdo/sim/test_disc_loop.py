import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

DW = 16
IDEAL = 40000
PG = 1


def to_signed(v, bits=32):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


async def pps(dut, err):
    dut.err.value = err & 0xFFFFFFFF
    dut.valid.value = 1
    await ClockCycles(dut.clk, 1)
    dut.valid.value = 0
    await ClockCycles(dut.clk, 2)
    await Timer(1, "ns")


@cocotb.test()
async def converges_then_holds(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.valid.value = 0
    dut.hold.value = 0
    await ClockCycles(dut.clk, 3)
    await Timer(1, "ns")
    assert int(dut.dac.value) == 1 << (DW - 1)

    for _ in range(400):
        err = (IDEAL - int(dut.dac.value)) * PG
        await pps(dut, err)

    assert dut.locked.value == 1
    settled = int(dut.dac.value)
    assert abs(settled - IDEAL) < 8, settled

    dut.hold.value = 1
    for _ in range(50):
        await pps(dut, 5000)
    assert int(dut.dac.value) == settled

    dut.hold.value = 0
    for _ in range(400):
        err = (IDEAL + 3000 - int(dut.dac.value)) * PG
        await pps(dut, err)
    assert abs(int(dut.dac.value) - (IDEAL + 3000)) < 8, int(dut.dac.value)
