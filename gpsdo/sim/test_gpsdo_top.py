import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

from uart_util import recv_byte

DIV = 234
PERIOD = 2000
TDC_N = 1200  #sim chains have no delay, fine saturates
OCXO_HZ = 740  #set in cocotb.mk, a 100 ns ocxo over one 74 us pps


async def drive_pps(dut):
    while True:
        dut.pps.value = 1
        await ClockCycles(dut.clk, 50)
        dut.pps.value = 0
        await ClockCycles(dut.clk, PERIOD - 50)


async def drive_ocxo(dut, half_ps):
    #half_ps is a list so a test can retune it while this runs
    while True:
        dut.ocxo.value = 1
        await Timer(half_ps[0], "ps")
        dut.ocxo.value = 0
        await Timer(half_ps[0], "ps")


async def read_line(dut):
    out = []
    while not out or out[-1] != 0x0A:
        out.append(await recv_byte(dut.clk, dut.uart_tx, DIV))
    return bytes(out)


HOLD = 4  #set in cocotb.mk


@cocotb.test()
async def streams_period_and_fine(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    cocotb.start_soon(drive_ocxo(dut, [50000]))
    dut.pps.value = 0
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, 5)
    cocotb.start_soon(drive_pps(dut))

    for i in range(3):
        line = await read_line(dut)
        assert len(line) == 27, line
        p, f, o, d = line.decode().split()
        assert int(p, 16) == PERIOD
        assert int(f, 16) == TDC_N
        assert len(o) == 8 and len(d) == 4
        if i:
            assert abs(int(o, 16) - OCXO_HZ) <= 1, line


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


@cocotb.test()
async def ocxo_error_steers_efc(dut):
    #a slow ocxo must raise the word, efc has a positive slope
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    half = [50500]
    cocotb.start_soon(drive_ocxo(dut, half))
    dut.pps.value = 0
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, 5)
    if (int(dut.led.value) >> 1) & 1 == 0:
        await tap_s1(dut)
    #no pps, no lines: let one already on the wire finish so reads align
    await ClockCycles(dut.clk, 28 * 10 * DIV)
    cocotb.start_soon(drive_pps(dut))

    async def word():
        _p, _f, o, d = (await read_line(dut)).decode().split()
        return int(o, 16), int(d, 16)

    await word()
    o, slow = await word()
    assert o < OCXO_HZ - 5, o
    _, slower = await word()
    assert slower > slow + 1000, (slow, slower)

    half[0] = 49500
    await word()
    o, fast = await word()
    assert o > OCXO_HZ + 5, o
    _, faster = await word()
    assert faster < fast - 1000, (fast, faster)

    #out of the window it leaves the word alone
    half[0] = 60000
    await word()
    _, a = await word()
    _, b = await word()
    assert a == b, (a, b)
