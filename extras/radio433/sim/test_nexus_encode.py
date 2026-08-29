import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

#scaled down in cocotb.mk
PULSE, ZERO, ONE, RESET, REPEATS = 5, 12, 25, 50, 2
GAP_MID = (ZERO + ONE) // 2
RESET_MID = (ONE + RESET) // 2


async def capture(dut, cycles):
    runs = []
    lvl = int(dut.bit_out.value)
    w = 0
    for _ in range(cycles):
        await ClockCycles(dut.clk, 1)
        b = int(dut.bit_out.value)
        if b == lvl:
            w += 1
        else:
            runs.append((lvl, w))
            lvl, w = b, 1
        if int(dut.done.value):
            runs.append((lvl, w))
            break
    return runs


def bits_from(runs):
    frames, bits = [], []
    for lvl, w in runs:
        if lvl == 0 and w >= RESET_MID:
            frames.append(bits)
            bits = []
        elif lvl == 0 and w >= 1:
            bits.append(1 if w >= GAP_MID else 0)
    return frames


@cocotb.test()
async def encodes_and_repeats(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.start.value = 0
    frame_bits = [1, 0, 1, 1, 0, 0, 1, 0] + [0, 1, 0, 1, 1, 0, 0, 1] + \
                 [1, 0, 0, 1, 0, 1, 1, 0] + [1, 1, 1, 1, 0, 1, 0, 1] + [0, 0, 1, 1]
    val = int("".join(str(b) for b in frame_bits), 2)
    dut.frame.value = val
    await ClockCycles(dut.clk, 3)

    dut.start.value = 1
    await ClockCycles(dut.clk, 1)
    dut.start.value = 0

    runs = await capture(dut, 4000)
    frames = bits_from(runs)

    assert len(frames) == REPEATS, f"want {REPEATS} repeats, got {len(frames)}"
    for f in frames:
        assert f == frame_bits, f
    assert int(dut.active.value) == 0, "active should drop at done"
