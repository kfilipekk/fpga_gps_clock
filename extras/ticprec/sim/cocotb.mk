SIM ?= icarus
TOPLEVEL_LANG ?= verilog

#uart_util is in mk/
export PYTHONPATH := $(abspath ../../../mk):$(PYTHONPATH)

VERILOG_SOURCES = $(abspath ../rtl/ticprec_top.v) \
                  $(abspath $(addprefix ../../../gpsdo/rtl/, tic.v tdc.v \
                    tdc_chain.v tdc_core.v ring_osc.v uart_tx.v))

#short chains, fast ring and uart
ifeq ($(COCOTB_TOPLEVEL),ticprec_top)
COMPILE_ARGS += -Pticprec_top.TDC_N=16 -Pticprec_top.RING_DIV=12 \
                -Pticprec_top.UART_DIV=8
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
