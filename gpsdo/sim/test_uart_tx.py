import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

from uart_util import recv_byte

DIV = 234


@cocotb.test()
async def sends_bytes(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.valid.value = 0
    dut.data.value = 0
    await ClockCycles(dut.clk, 2)
    assert dut.ready.value == 1
    assert dut.tx.value == 1

    for byte in (0x55, 0x00, 0xFF, 0x0A):
        recv = cocotb.start_soon(recv_byte(dut.clk, dut.tx, DIV))
        dut.data.value = byte
        dut.valid.value = 1
        await ClockCycles(dut.clk, 1)
        await Timer(1, "ns")
        dut.valid.value = 0
        assert dut.ready.value == 0
        got = await recv
        assert got == byte
        await ClockCycles(dut.clk, DIV)
        await Timer(1, "ns")
        assert dut.ready.value == 1
