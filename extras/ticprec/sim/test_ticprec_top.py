import cocotb
from cocotb.clock import Clock

from uart_util import recv_byte

N = 16  #set in cocotb.mk


@cocotb.test()
async def same_edge_lines(dut):
    cocotb.start_soon(Clock(dut.clk, 37, "ns").start())
    for _ in range(4):
        s = ""
        while not s.endswith("\n"):
            s += chr(await recv_byte(dut.clk, dut.uart_tx, 8))
        f = s.split()
        assert len(s) == 17 and len(f) == 3, repr(s)
        assert int(f[0], 16) == 0, s
        assert int(f[1], 16) == N and int(f[2], 16) == N, s
