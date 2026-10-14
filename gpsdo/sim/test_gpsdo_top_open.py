import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from test_gpsdo_top import DIV, OCXO_HZ, drive_ocxo, drive_pps, read_line

FIXED = 40000  #set in cocotb.mk


@cocotb.test()
async def open_loop_holds_efc(dut):
    #a slow ocxo would raise the word if the loop were closed
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    cocotb.start_soon(drive_ocxo(dut, [50500]))
    dut.pps.value = 0
    dut.btn_s1.value = 1
    await ClockCycles(dut.clk, 5)
    cocotb.start_soon(drive_pps(dut))

    words = []
    for _ in range(4):
        _p, _f, o, d = (await read_line(dut)).decode().split()
        words.append(int(d, 16))
    assert int(o, 16) < OCXO_HZ - 5, o
    assert words == [FIXED] * 4, words
