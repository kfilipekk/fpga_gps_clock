SIM ?= icarus
TOPLEVEL_LANG ?= verilog

#uart_util is in mk/
export PYTHONPATH := $(abspath ../../../mk):$(PYTHONPATH)

#local rtl plus what it reuses from gpsdo
VERILOG_SOURCES = $(abspath $(wildcard ../rtl/*.v)) \
                  $(abspath ../../../gpsdo/rtl/uart_tx.v) \
                  $(abspath ../../../gpsdo/rtl/pps_capture.v) \
                  $(abspath ../../../gpsdo/rtl/rf_stamp.v) \
                  $(abspath ../../../gpsdo/rtl/tdc.v) \
                  $(abspath ../../../gpsdo/rtl/tdc_chain.v) \
                  $(abspath ../../../gpsdo/rtl/tdc_core.v)

#tiny params so a synthetic packet fits in a few hundred cycles
ifeq ($(COCOTB_TOPLEVEL),ook_rx)
COMPILE_ARGS += -Pook_rx.IDLE=40
endif
ifeq ($(COCOTB_TOPLEVEL),radio433_top)
COMPILE_ARGS += -Pradio433_top.IDLE=40 -Pradio433_top.TDC_N=16 \
                -Pradio433_top.GLITCH_K=5 -Pradio433_top.PWM_THRESH=20 \
                -Pradio433_top.SYNC=165 -Pradio433_top.SYNC_LEN=8 \
                -Pradio433_top.PAYLOAD_LEN=8
endif
#the real decode params, idle trimmed
ifeq ($(COCOTB_TEST_MODULES),test_radio433_top_hw)
COMPILE_ARGS += -Pradio433_top.IDLE=20000 -Pradio433_top.TDC_N=16 \
                -Pradio433_top.GLITCH_K=6750 -Pradio433_top.PWM_THRESH=20250 \
                -Pradio433_top.SYNC=54161 -Pradio433_top.SYNC_LEN=16 \
                -Pradio433_top.PAYLOAD_LEN=32
endif
#idle past the reset gap, so the repeats stay one packet
ifeq ($(COCOTB_TEST_MODULES),test_radio433_top_transcode)
COMPILE_ARGS += -Pradio433_top.IDLE=60 -Pradio433_top.TDC_N=16 \
                -Pradio433_top.GLITCH_K=5 \
                -Pradio433_top.NX_PULSE_MIN=3 -Pradio433_top.NX_PULSE_MAX=16 \
                -Pradio433_top.NX_ONE_MIN=18 -Pradio433_top.NX_RESET_MIN=38 \
                -Pradio433_top.NX_PULSE=8 -Pradio433_top.NX_ZERO=12 \
                -Pradio433_top.NX_ONE=25 -Pradio433_top.NX_RESET=45 \
                -Pradio433_top.NX_REPEATS=2
endif
#nrz, bit slot longer than glitch_k
ifeq ($(COCOTB_TEST_MODULES),test_radio433_top_nrz)
COMPILE_ARGS += -Pradio433_top.IDLE=1000 -Pradio433_top.TDC_N=16 \
                -Pradio433_top.GLITCH_K=50 -Pradio433_top.NRZ=1 \
                -Pradio433_top.BIT_CYCLES=200 -Pradio433_top.SYNC=54161 \
                -Pradio433_top.SYNC_LEN=16 -Pradio433_top.PAYLOAD_LEN=32
endif
ifeq ($(COCOTB_TOPLEVEL),spi_cfg)
COMPILE_ARGS += -Pspi_cfg.SETTLE=5 -Pspi_cfg.DIV=2
endif
ifeq ($(COCOTB_TOPLEVEL),glitch_filt)
COMPILE_ARGS += -Pglitch_filt.K=10
endif
ifeq ($(COCOTB_TOPLEVEL),pwm_slice)
COMPILE_ARGS += -Ppwm_slice.THRESH=50
endif
ifeq ($(COCOTB_TEST_MODULES),test_pwm_slice_adapt)
COMPILE_ARGS += -Ppwm_slice.THRESH=50 -Ppwm_slice.ADAPT=1
endif
ifeq ($(COCOTB_TEST_MODULES),test_sync_frame)
COMPILE_ARGS += -Psync_frame.SYNC=165 -Psync_frame.SYNC_LEN=8 \
                -Psync_frame.PAYLOAD_LEN=8
endif
ifeq ($(COCOTB_TEST_MODULES),test_sync_frame_crc)
COMPILE_ARGS += -Psync_frame.SYNC=165 -Psync_frame.SYNC_LEN=8 \
                -Psync_frame.PAYLOAD_LEN=16 -Psync_frame.CRC_CHECK=1
endif
ifeq ($(COCOTB_TOPLEVEL),nrz_sample)
COMPILE_ARGS += -Pnrz_sample.BIT_CYCLES=20
endif
ifeq ($(COCOTB_TOPLEVEL),manch_decode)
COMPILE_ARGS += -Pmanch_decode.HALF=10
endif
ifeq ($(COCOTB_TOPLEVEL),nexus_decode)
COMPILE_ARGS += -Pnexus_decode.PULSE_MIN=3 -Pnexus_decode.PULSE_MAX=10 \
                -Pnexus_decode.ONE_MIN=20 -Pnexus_decode.RESET_MIN=40
endif
ifeq ($(COCOTB_TOPLEVEL),nexus_encode)
COMPILE_ARGS += -Pnexus_encode.PULSE=5 -Pnexus_encode.ZERO=12 \
                -Pnexus_encode.ONE=25 -Pnexus_encode.RESET=50 \
                -Pnexus_encode.REPEATS=2
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
