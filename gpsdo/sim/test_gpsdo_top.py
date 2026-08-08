import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

from uart_util import recv_byte

DIV = 234
PERIOD = 2000
TDC_N = 1200  #sim chains have no delay, fine saturates


async def drive_pps(dut):
    while True:
        dut.pps.value = 1
        await ClockCycles(dut.clk, 50)
        dut.pps.value = 0
        await ClockCycles(dut.clk, PERIOD - 50)


HOLD = 4  #set in cocotb.mk


@cocotb.test()
async def streams_period_and_fine(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, 5)
    cocotb.start_soon(drive_pps(dut))

    for _ in range(2):
        line = bytes([await recv_byte(dut.clk, dut.uart_tx, DIV) for _ in range(13)])
        assert line[8:9] == b" "
        assert line[12] == 0x0A
        assert int(line[:8].decode(), 16) == PERIOD
        assert int(line[9:12].decode(), 16) == TDC_N


@cocotb.test()
async def s1_hands_the_tdc_to_the_ring(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, HOLD * 3)
    await Timer(1, "ns")
    assert (int(dut.led.value) >> 1) & 1 == 1

    dut.btn_s1.value = 0
    await ClockCycles(dut.clk, HOLD + 6)
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, HOLD + 6)
    await Timer(1, "ns")
    assert (int(dut.led.value) >> 1) & 1 == 0

    cocotb.start_soon(drive_pps(dut))
    await ClockCycles(dut.clk, 400)


LOSS = 300  #set in cocotb.mk


async def tap_s1(dut):
    dut.btn_s1.value = 0
    await ClockCycles(dut.clk, HOLD + 6)
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, HOLD + 6)
    await Timer(1, "ns")


@cocotb.test()
async def pps_loss_trips_holdover(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, 5)

    #tests share one sim with no reset, so force run mode
    if (int(dut.led.value) >> 1) & 1 == 0:
        await tap_s1(dut)

    for _ in range(4):
        dut.pps.value = 1
        await ClockCycles(dut.clk, 50)
        dut.pps.value = 0
        await ClockCycles(dut.clk, 150)
    await Timer(1, "ns")
    assert (int(dut.led.value) >> 3) & 1 == 1

    await ClockCycles(dut.clk, LOSS + 10)
    await Timer(1, "ns")
    assert (int(dut.led.value) >> 3) & 1 == 0
