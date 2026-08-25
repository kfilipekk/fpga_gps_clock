import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

IDLE = 40  #set in cocotb.mk


async def run(dut, level, width):
    dut.data.value = level
    await ClockCycles(dut.clk, width)


@cocotb.test()
async def measures_runs_and_frames_packets(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    dut.data.value = 0

    got = []
    sops = []
    eops = []
    started = {"v": False}

    async def monitor():
        while True:
            await RisingEdge(dut.clk)
            await Timer(1, "ns")
            if dut.eop.value == 1:
                eops.append(1)
            if dut.sop.value == 1:
                sops.append(1)
                started["v"] = True
                continue
            if started["v"] and dut.run_valid.value == 1:
                got.append((int(dut.run_level.value), int(dut.run_width.value)))

    cocotb.start_soon(monitor())

    await run(dut, 0, IDLE + 20)
    widths = [(1, 30), (0, 12), (1, 18), (0, 12), (1, 30)]
    for level, w in widths:
        await run(dut, level, w)
    await run(dut, 0, IDLE + 20)
    await ClockCycles(dut.clk, 5)

    assert len(sops) == 1, sops
    assert len(eops) == 1, eops
    assert len(got) >= len(widths), got
    for (dl, dw), (gl, gw) in zip(widths, got):
        assert gl == dl, (dl, gl)
        assert abs(gw - dw) <= 1, (dw, gw)
