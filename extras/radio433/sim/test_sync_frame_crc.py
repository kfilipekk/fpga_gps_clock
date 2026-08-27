import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

SYNC = 0xA5
SYNC_LEN = 8
PAYLOAD_LEN = 16


def bits(v, n):
    return [(v >> i) & 1 for i in range(n - 1, -1, -1)]


def crc8(data_bits, poly=0x07, init=0x00):
    #same recurrence as sync_frame
    crc = init
    for b in data_bits:
        msb = (crc >> 7) & 1
        crc = (crc << 1) & 0xFF
        if msb ^ b:
            crc ^= poly
    return crc


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
async def good_crc_frames_bad_crc_dropped(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.db.value = 0
    dut.db_valid.value = 0
    dut.sop.value = 0
    dut.eop.value = 0
    await ClockCycles(dut.clk, 3)

    payloads = await watch(dut)

    data = 0x3C
    good = crc8(bits(data, 8))
    exp = (data << 8) | good

    await pulse(dut, "sop")
    await send(dut, bits(SYNC, SYNC_LEN) + bits(data, 8) + bits(good, 8))
    await ClockCycles(dut.clk, 3)
    assert payloads == [exp], (payloads, hex(exp))

    await pulse(dut, "sop")
    await send(dut, bits(SYNC, SYNC_LEN) + bits(data, 8) + bits(good ^ 0xFF, 8))
    await ClockCycles(dut.clk, 3)
    assert payloads == [exp], payloads

    await pulse(dut, "sop")
    await send(dut, bits(SYNC, SYNC_LEN) + bits(data, 8) + bits(good, 8))
    await ClockCycles(dut.clk, 3)
    assert payloads == [exp, exp], payloads
