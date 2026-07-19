#yosys, nextpnr, gowin_pack and openFPGALoader

ROOT  := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
BOARD ?= tangnano9k
BUILD ?= build
FREQ  ?= 27
PARAMS ?=

include $(ROOT)/mk/$(BOARD).mk

BITSTREAM = $(BUILD)/$(TOP).fs

all: $(BITSTREAM)

$(BUILD)/$(TOP).json: $(SOURCES)
	@mkdir -p $(BUILD)
	yosys -q -l $(BUILD)/yosys.log -p "read_verilog $(SOURCES); $(PARAMS); synth_gowin -top $(TOP) -json $@"

$(BUILD)/pins.cst: $(CST) $(CST_EXTRA)
	@mkdir -p $(BUILD)
	cat $^ > $@

$(BUILD)/$(TOP)_pnr.json: $(BUILD)/$(TOP).json $(BUILD)/pins.cst
	nextpnr-himbaechel --json $< --write $@ --freq $(FREQ) \
		--device $(DEVICE) --vopt family=$(FAMILY) --vopt cst=$(BUILD)/pins.cst

$(BITSTREAM): $(BUILD)/$(TOP)_pnr.json
	gowin_pack -d $(FAMILY) -o $@ $<

#sram, gone on power cycle
flash: $(BITSTREAM)
	openFPGALoader -b $(BOARD) $(BITSTREAM)

#spi flash
flash-persist: $(BITSTREAM)
	openFPGALoader -b $(BOARD) -f $(BITSTREAM)

#init at declaration is fine on an fpga
lint:
	verilator --lint-only -Wall -Wno-PROCASSINIT --top-module $(TOP) $(SOURCES)

sim:
	$(MAKE) -C sim

formal:
	@for f in $(wildcard formal/*.sby); do \
		(cd formal && sby -f $$(basename $$f)) || exit 1; done

clean:
	rm -rf $(BUILD)
	-@$(MAKE) -C sim clean 2>/dev/null

.PHONY: all flash flash-persist lint sim formal clean
