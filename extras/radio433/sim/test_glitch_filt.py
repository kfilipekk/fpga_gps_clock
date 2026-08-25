import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

K = 10  #set in cocotb.mk

async def hold(dut, level, n):
    dut.din.value = level
    await ClockCycles(dut.clk, n)


def runs(samples):
    out = []
    cur, cnt = None, 0
    for v in samples:
        if v != cur:
            if cur is not None and cnt:
                out.append((cur, cnt))
            cur, cnt = v, 1
        else:
            cnt += 1
    if cnt:
        out.append((cur, cnt))
    return out


async def watch(dut):
    samples = []

    async def w():
        while True:
            await RisingEdge(dut.clk)
            await Timer(1, "ns")
            samples.append(int(dut.out.value))

    cocotb.start_soon(w())
    return samples


@cocotb.test()
async def rejects_glitches_and_preserves_pulses(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.din.value = 0
    await ClockCycles(dut.clk, 5)
    assert dut.out.value == 0

    samples = await watch(dut)

    await hold(dut, 1, 2)
    await hold(dut, 0, 2)
    await hold(dut, 1, K // 2)
    await hold(dut, 0, 3)
    await hold(dut, 1, K - 1)
    await hold(dut, 0, 3)
    assert dut.out.value == 0

    await hold(dut, 1, 30)
    await hold(dut, 0, 30)
    await hold(dut, 1, 40)
    await hold(dut, 0, 40)
    await ClockCycles(dut.clk, 10)

    out = runs(samples)
    highs = [(lvl, w) for lvl, w in out if lvl == 1]
    assert len(highs) == 2, out
    assert abs(highs[0][1] - 30) <= 2, highs
    assert abs(highs[1][1] - 40) <= 2, highs
    assert out[0][0] == 0 and out[-1][0] == 0, out


@cocotb.test()
async def fills_subk_dropouts(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.din.value = 0
    await ClockCycles(dut.clk, 5)

    samples = await watch(dut)

    await hold(dut, 1, 20)
    await hold(dut, 0, K // 2)
    await hold(dut, 1, 20)
    await hold(dut, 0, 30)
    await ClockCycles(dut.clk, 5)

    out = runs(samples)
    assert len(out) == 3, out
    assert out[1] == (1, 45), out
    assert out[2][0] == 0, out
