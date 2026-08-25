import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


async def cc1101_slave(dut, regs, strobes):
    #sample mosi on sck rising, so low means ready
    prev_sck = 0
    prev_csn = 1
    bitcnt = 0
    cur = 0
    bytepos = 0
    header = None
    while True:
        await RisingEdge(dut.clk)
        csn = int(dut.csn.value)
        sck = int(dut.sck.value)
        if prev_csn == 1 and csn == 0:
            bitcnt = cur = bytepos = 0
            header = None
            dut.miso.value = 0
        if prev_csn == 0 and csn == 1:
            dut.miso.value = 1
        if csn == 0 and prev_sck == 0 and sck == 1:
            cur = ((cur << 1) | int(dut.mosi.value)) & 0xFF
            bitcnt += 1
            if bitcnt == 8:
                if bytepos == 0:
                    header = cur
                    if header >= 0x30:
                        strobes.append(header)
                else:
                    regs[header] = cur
                bytepos += 1
                bitcnt = cur = 0
        prev_sck, prev_csn = sck, csn


@cocotb.test()
async def configures_the_cc1101(dut):
    regs, strobes = {}, []
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.miso.value = 1
    dut.mode.value = 0
    dut.start.value = 0
    cocotb.start_soon(cc1101_slave(dut, regs, strobes))

    for _ in range(200000):
        await RisingEdge(dut.clk)
        if int(dut.done.value) == 1:
            break
    assert int(dut.done.value) == 1, "config never finished"

    assert regs.get(0x02) == 0x0D, f"iocfg0 = {regs.get(0x02)}"
    assert regs.get(0x12) == 0x30, f"mdmcfg2 = {regs.get(0x12)}"
    assert regs.get(0x0D) == 0x10, f"freq2 = {regs.get(0x0D)}"
    assert regs.get(0x0F) == 0x71, f"freq0 = {regs.get(0x0F)}"
    assert len(regs) == 27, f"wrote {len(regs)} registers, want 27"
    assert 0x30 in strobes, "sres not issued"
    assert 0x34 in strobes, "srx not issued"


@cocotb.test()
async def retriggers_tx_config(dut):
    regs, strobes = {}, []
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.miso.value = 1
    dut.mode.value = 0
    dut.start.value = 0
    cocotb.start_soon(cc1101_slave(dut, regs, strobes))

    for _ in range(200000):
        await RisingEdge(dut.clk)
        if int(dut.done.value) == 1:
            break
    assert int(dut.done.value) == 1, "config never finished"

    dut.mode.value = 1
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0
    regs.clear(); strobes.clear()
    for _ in range(200000):
        await RisingEdge(dut.clk)
        if int(dut.done.value) == 0:
            break
    assert int(dut.done.value) == 0, "re-trigger never started"
    for _ in range(200000):
        await RisingEdge(dut.clk)
        if int(dut.done.value) == 1:
            break
    assert int(dut.done.value) == 1, "tx config never finished"

    assert regs.get(0x02) == 0x2E, f"tx iocfg0 = {regs.get(0x02)}"
    assert len(regs) == 27, f"tx wrote {len(regs)} registers, want 27"
    assert 0x35 in strobes, "stx not issued"
    assert 0x34 not in strobes, "srx issued in tx mode"
