#one run per module, `make xo_meter` for just one

UNITS = xo_meter xocal_top

all: $(UNITS)

$(UNITS):
	$(MAKE) -f cocotb.mk COCOTB_TOPLEVEL=$@ COCOTB_TEST_MODULES=test_$@ \
		SIM_BUILD=sim_build/$@ COCOTB_RESULTS_FILE=sim_build/$@/results.xml

clean:
	rm -rf sim_build __pycache__

.PHONY: all clean $(UNITS)
