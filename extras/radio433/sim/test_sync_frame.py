import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

SYNC = 0xA5  #set in cocotb.mk
SYNC_LEN = 8
PAYLOAD_LEN = 8


def bits(v, n):
    return [(v >> i) & 1 for i in range(n - 1, -1, -1)]


async def send(dut, vals):
    for b in vals:
        dut.db.value = b
        dut.db_valid.value = 1
        await ClockCycles(dut.clk, 1)
        dut.db_valid.value = 0
        await ClockCycles(dut.clk, 1)


async def pulse(dut, sig):
    getattr(dut, sig).value = 1
    await ClockCycles(dut.clk, 1)
    getattr(dut, sig).value = 0
    await ClockCycles(dut.clk, 1)


async def watch(dut):
    payloads = []

    async def w():
        while True:
            await RisingEdge(dut.clk)
            await Timer(1, "ns")
            if dut.payload_valid.value == 1:
                payloads.append(int(dut.payload.value))

    cocotb.start_soon(w())
    return payloads


@cocotb.test()
async def no_false_match_on_noise(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.db.value = 0
    dut.db_valid.value = 0
    dut.sop.value = 0
    dut.eop.value = 0
    await ClockCycles(dut.clk, 3)

    payloads = await watch(dut)

    await send(dut, [1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1])
    await ClockCycles(dut.clk, 3)

    assert payloads == [], payloads


@cocotb.test()
async def frames_on_sync_and_resets_on_eop(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.db.value = 0
    dut.db_valid.value = 0
    dut.sop.value = 0
    dut.eop.value = 0
    await ClockCycles(dut.clk, 3)

    payloads = await watch(dut)

    await pulse(dut, "sop")
    await send(dut, bits(SYNC, SYNC_LEN) + bits(0x3C, PAYLOAD_LEN))
    await ClockCycles(dut.clk, 3)
    assert payloads == [0x3C], payloads

    await pulse(dut, "sop")
    await send(dut, bits(SYNC, SYNC_LEN) + [1, 0, 1])
    await pulse(dut, "eop")
    await send(dut, [0, 1, 0, 0, 1, 0, 1, 1])
    await ClockCycles(dut.clk, 3)
    assert payloads == [0x3C], payloads

    await pulse(dut, "sop")
    await send(dut, bits(SYNC, SYNC_LEN) + bits(0x5A, PAYLOAD_LEN))
    await ClockCycles(dut.clk, 3)
    assert payloads == [0x3C, 0x5A], payloads
