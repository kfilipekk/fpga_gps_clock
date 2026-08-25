import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

DIV = 234


async def send_byte(dut, val):
    dut.rx.value = 0
    await ClockCycles(dut.clk, DIV)
    for i in range(8):
        dut.rx.value = (val >> i) & 1
        await ClockCycles(dut.clk, DIV)
    dut.rx.value = 1
    await ClockCycles(dut.clk, DIV)


@cocotb.test()
async def receives_a_byte(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.rx.value = 1
    await ClockCycles(dut.clk, 10)

    got = []

    async def rx():
        for _ in range(12 * DIV):
            await ClockCycles(dut.clk, 1)
            if dut.valid.value:
                got.append(int(dut.data.value))

    cocotb.start_soon(rx())
    cocotb.start_soon(send_byte(dut, ord("T")))
    await ClockCycles(dut.clk, 12 * DIV)

    assert got == [ord("T")], got


@cocotb.test()
async def ignores_a_false_start(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.rx.value = 1
    await ClockCycles(dut.clk, 10)

    got = []

    async def rx():
        for _ in range(12 * DIV):
            await ClockCycles(dut.clk, 1)
            if dut.valid.value:
                got.append(int(dut.data.value))

    cocotb.start_soon(rx())

    dut.rx.value = 0
    await ClockCycles(dut.clk, DIV // 4)
    dut.rx.value = 1
    await ClockCycles(dut.clk, DIV)
    cocotb.start_soon(send_byte(dut, 0x2A))
    await ClockCycles(dut.clk, 12 * DIV)

    assert got == [0x2A], got
