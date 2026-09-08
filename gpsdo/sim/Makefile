#one run per module, `make uart_tx` for just one

UNITS = uart_tx pps_capture tdc_core tdc tdc_wu cal_mon tic rf_stamp \
        btn_toggle sd_dac disc_loop gpsdo_top

all: $(UNITS) disc_loop_seu disc_loop_seu_tmr

$(UNITS):
	$(MAKE) -f cocotb.mk COCOTB_TOPLEVEL=$@ COCOTB_TEST_MODULES=test_$@ \
		SIM_BUILD=sim_build/$@ COCOTB_RESULTS_FILE=sim_build/$@/results.xml

#upset campaign, plain and tmr
disc_loop_seu disc_loop_seu_tmr:
	$(MAKE) -f cocotb.mk COCOTB_TOPLEVEL=disc_loop COCOTB_TEST_MODULES=test_disc_loop_seu \
		SIM_BUILD=sim_build/$@ COCOTB_RESULTS_FILE=sim_build/$@/results.xml

clean:
	rm -rf sim_build __pycache__

.PHONY: all clean $(UNITS) disc_loop_seu disc_loop_seu_tmr
