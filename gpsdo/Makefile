TOP     = gpsdo_top
SOURCES = rtl/gpsdo_top.v rtl/pps_capture.v rtl/uart_tx.v \
          rtl/tdc.v rtl/tdc_chain.v rtl/tdc_core.v \
          rtl/ring_osc.v rtl/btn_toggle.v \
          rtl/disc_loop.v rtl/tmr_reg.v rtl/sd_dac.v
CST_EXTRA = gpsdo.cst

include ../mk/gowin.mk

#modules not in a bitstream get linted on their own
lint: lint-lib
lint-lib:
	verilator --lint-only -Wall -Wno-PROCASSINIT --top-module tdc_wu \
		rtl/tdc_wu.v rtl/tdc.v rtl/tdc_chain.v rtl/tdc_core.v
	verilator --lint-only -Wall -Wno-PROCASSINIT --top-module cal_mon \
		rtl/cal_mon.v rtl/tdc.v rtl/tdc_chain.v rtl/tdc_core.v rtl/ring_osc.v

.PHONY: lint-lib
