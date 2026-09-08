#one random bit flip in the locked loop, then 30 more pps
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

DW, IW = 16, 48
IDEAL = 40000
LOCK_ERR = 4  #set in cocotb.mk
TRIALS = 200
AFTER = 30


def to_signed(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


async def pps(dut):
    err = IDEAL - int(dut.dac.value)
    dut.err.value = err & 0xFFFFFFFF
    dut.valid.value = 1
    await ClockCycles(dut.clk, 1)
    dut.valid.value = 0
    await ClockCycles(dut.clk, 2)
    await Timer(1, "ns")
    return err


def regs(dut, tmr):
    if tmr:
        return [getattr(dut.t, f"u_i{k}").r for k in range(3)], \
               [getattr(dut.t, f"u_d{k}").r for k in range(3)]
    return [dut.s.i0], [dut.s.d0]


@cocotb.test()
async def upset_campaign(dut):
    tmr = int(dut.TMR.value)
    dut.valid.value = 0  #settle before the first edge or the vote passes x
    dut.hold.value = 0
    dut.err.value = 0
    await Timer(1, "ns")
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    await ClockCycles(dut.clk, 3)
    for _ in range(400):
        await pps(dut)
    assert dut.locked.value == 1
    integs, dacs = regs(dut, tmr)
    good_i = int(integs[0].value)
    good_d = int(dacs[0].value)

    random.seed(7)
    tally = {"masked": 0, "transient": 0, "failure": 0}
    worst = 0
    for _ in range(TRIALS):
        for r in integs:
            r.value = good_i
        for r in dacs:
            r.value = good_d
        await ClockCycles(dut.clk, 2)

        bit = random.randrange(IW + DW)
        copy = random.randrange(3)
        await ClockCycles(dut.clk, random.randrange(3))
        if bit < IW:
            r = integs[copy % len(integs)]
            r.value = to_signed(int(r.value) ^ (1 << bit), IW) & ((1 << IW) - 1)
        else:
            r = dacs[copy % len(dacs)]
            r.value = int(r.value) ^ (1 << (bit - IW))

        errs = [await pps(dut) for _ in range(AFTER)]
        out = [abs(e) >= LOCK_ERR for e in errs]
        worst = max(worst, max(abs(e) for e in errs))
        if out[-1]:
            tally["failure"] += 1
        elif any(out):
            tally["transient"] += 1
        else:
            tally["masked"] += 1

    dut._log.info(f"TMR={tmr} {TRIALS} upsets: {tally}, worst |err| {worst}")
    if tmr:
        assert tally["failure"] == 0 and tally["transient"] == 0, tally
    else:
        assert tally["failure"] > 0, tally
