from cocotb.triggers import ClockCycles, FallingEdge


async def recv_byte(clk, tx, div):
    #wait for the start bit then sample mid-bit
    await FallingEdge(tx)
    await ClockCycles(clk, div // 2)
    assert tx.value == 0
    val = 0
    for i in range(8):
        await ClockCycles(clk, div)
        val |= int(tx.value) << i
    await ClockCycles(clk, div)
    assert tx.value == 1  #stop bit
    return val
