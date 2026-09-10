SIM ?= icarus
TOPLEVEL_LANG ?= verilog

#uart_util is in mk/
export PYTHONPATH := $(abspath ../../../mk):$(PYTHONPATH)

#local rtl plus what it reuses
VERILOG_SOURCES = $(abspath $(wildcard ../rtl/*.v)) \
                  $(abspath ../../radio433/rtl/spi_cfg.v) \
                  $(abspath ../../../gpsdo/rtl/uart_tx.v) \
                  $(abspath ../../../gpsdo/rtl/pps_capture.v)

#short settle, fast uart, a 3000 cycle second
ifeq ($(COCOTB_TOPLEVEL),xocal_top)
COMPILE_ARGS += -Pxocal_top.SETTLE=5 -Pxocal_top.SEC=3000 \
                -Pxocal_top.UART_DIV=8
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
