import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

BIT = 20  #set in cocotb.mk


async def send(dut, bits):
    for b in bits:
        dut.sig.value = b
        await ClockCycles(dut.clk, BIT)


def sublist(small, big):
    for i in range(len(big) - len(small) + 1):
        if big[i:i + len(small)] == small:
            return True
    return False


@cocotb.test()
async def recovers_nrz_bits(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.sig.value = 0
    await ClockCycles(dut.clk, BIT)

    got = []

    async def mon():
        while True:
            await RisingEdge(dut.clk)
            await Timer(1, "ns")
            if dut.db_valid.value == 1:
                got.append(int(dut.db.value))

    cocotb.start_soon(mon())

    pattern = [1, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 0, 1]
    await send(dut, pattern)
    await ClockCycles(dut.clk, BIT)

    assert sublist(pattern, got), (pattern, got)
