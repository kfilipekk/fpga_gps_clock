#one run per module, `make ook_rx` for just one

UNITS = ook_rx spi_cfg glitch_filt pwm_slice sync_frame nrz_sample uart_rx \
        manch_decode

all: $(UNITS) pwm_slice_adapt sync_frame_crc

$(UNITS):
	$(MAKE) -f cocotb.mk COCOTB_TOPLEVEL=$@ COCOTB_TEST_MODULES=test_$@ \
		SIM_BUILD=sim_build/$@ COCOTB_RESULTS_FILE=sim_build/$@/results.xml

#same rtl, other params
pwm_slice_adapt:
	$(MAKE) -f cocotb.mk COCOTB_TOPLEVEL=pwm_slice COCOTB_TEST_MODULES=test_$@ \
		SIM_BUILD=sim_build/$@ COCOTB_RESULTS_FILE=sim_build/$@/results.xml

sync_frame_crc:
	$(MAKE) -f cocotb.mk COCOTB_TOPLEVEL=sync_frame COCOTB_TEST_MODULES=test_$@ \
		SIM_BUILD=sim_build/$@ COCOTB_RESULTS_FILE=sim_build/$@/results.xml

clean:
	rm -rf sim_build __pycache__

.PHONY: all clean $(UNITS) pwm_slice_adapt sync_frame_crc
