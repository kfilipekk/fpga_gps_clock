import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

#scaled down in cocotb.mk
DIV = 234
IDLE = 60
NPULSE, NZERO, NONE, NRESET = 8, 12, 25, 45
GAP_MID = (NZERO + NONE) // 2
RESET_MID = (NONE + NRESET) // 2


async def hold(dut, level, n):
    dut.cc1101_data.value = level
    await ClockCycles(dut.clk, n)


async def send_byte(dut, val):
    dut.uart_rx.value = 0
    await ClockCycles(dut.clk, DIV)
    for i in range(8):
        dut.uart_rx.value = (val >> i) & 1
        await ClockCycles(dut.clk, DIV)
    dut.uart_rx.value = 1
    await ClockCycles(dut.clk, DIV)


async def feed_nexus(dut, bits):
    for b in bits:
        await hold(dut, 1, NPULSE)
        await hold(dut, 0, NONE if b else NZERO)
    await hold(dut, 1, NPULSE)


def bits_from(runs):
    frames, bits = [], []
    for lvl, w in runs:
        if lvl == 0 and w >= RESET_MID:
            frames.append(bits)
            bits = []
        elif lvl == 0 and w >= 3:
            bits.append(1 if w >= GAP_MID else 0)
    return frames


@cocotb.test()
async def transcodes_a_nexus_frame(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.pps.value = 0
    dut.cc1101_data.value = 0
    dut.uart_rx.value = 1
    dut.cc1101_miso.value = 0
    await ClockCycles(dut.clk, 5)

    frame = [1, 0, 1, 0, 0, 1, 1, 0] + [0, 1, 0, 0, 1, 1, 0, 1] + \
            [1, 0, 1, 0, 0, 0, 1, 1] + [1, 1, 1, 1, 0, 0, 1, 0] + [1, 0, 1, 1]

    await hold(dut, 0, IDLE + 20)
    await feed_nexus(dut, frame)
    await hold(dut, 0, NRESET)
    await feed_nexus(dut, frame)
    await hold(dut, 0, IDLE + 20)

    await ClockCycles(dut.clk, 5000)

    dut.cc1101_data.value = "z"
    seen = []

    async def sample(n):
        cur, w = None, 0
        for _ in range(n):
            v = str(dut.cc1101_data.value)
            if v in ("0", "1"):
                lvl = int(v)
                if lvl == cur:
                    w += 1
                else:
                    if cur is not None:
                        seen.append((cur, w))
                    cur, w = lvl, 1
            else:
                if cur is not None:
                    seen.append((cur, w))
                    cur, w = None, 0
            await ClockCycles(dut.clk, 1)
        if cur is not None:
            seen.append((cur, w))

    cocotb.start_soon(sample(60000))
    await send_byte(dut, ord("C"))
    await ClockCycles(dut.clk, 61000)

    got = [r for r in seen if r[1] >= 3]
    frames = bits_from(got)
    assert len(frames) == 2, (len(frames), got)
    for f in frames:
        assert f == frame, (f, frame)
