SIM ?= icarus
TOPLEVEL_LANG ?= verilog

#uart_util is in mk/
export PYTHONPATH := $(abspath ../../mk):$(PYTHONPATH)

VERILOG_SOURCES = $(abspath $(wildcard ../rtl/*.v))

#narrow counter so it wraps
ifeq ($(COCOTB_TOPLEVEL),pps_capture)
COMPILE_ARGS += -Ppps_capture.W=16
endif

#short chains
ifeq ($(COCOTB_TOPLEVEL),tdc_core)
COMPILE_ARGS += -Ptdc_core.N=16
endif
ifeq ($(COCOTB_TOPLEVEL),tdc)
COMPILE_ARGS += -Ptdc.N=32
endif

#short debounce
ifeq ($(COCOTB_TOPLEVEL),btn_toggle)
COMPILE_ARGS += -Pbtn_toggle.HOLD=4
endif
ifeq ($(COCOTB_TOPLEVEL),gpsdo_top)
COMPILE_ARGS += -Pgpsdo_top.BTN_HOLD=4 -Pgpsdo_top.LOSS=300
endif

#narrow dac
ifeq ($(COCOTB_TOPLEVEL),sd_dac)
COMPILE_ARGS += -Psd_dac.W=8
endif

#small gains so the loop settles quickly
ifeq ($(COCOTB_TOPLEVEL),disc_loop)
COMPILE_ARGS += -Pdisc_loop.KP=3 -Pdisc_loop.KI=5 -Pdisc_loop.LOCK_ERR=4
endif
ifeq ($(SIM_BUILD),sim_build/disc_loop_seu_tmr)
COMPILE_ARGS += -Pdisc_loop.TMR=1
endif

#short chains
ifeq ($(COCOTB_TOPLEVEL),tdc_wu)
COMPILE_ARGS += -Ptdc_wu.N=32
endif
ifeq ($(COCOTB_TOPLEVEL),cal_mon)
COMPILE_ARGS += -Pcal_mon.N=8 -Pcal_mon.DIV=4 -Pcal_mon.DECIMATE=4
endif
ifeq ($(COCOTB_TOPLEVEL),tic)
COMPILE_ARGS += -Ptic.N=16
endif
ifeq ($(COCOTB_TOPLEVEL),rf_stamp)
COMPILE_ARGS += -Prf_stamp.N=16
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
