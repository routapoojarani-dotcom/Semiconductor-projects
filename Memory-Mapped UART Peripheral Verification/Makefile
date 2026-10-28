# ---------------------------------------------------------------------------
# FPGA Digital Systems Verification Lab
#
# Thin wrapper around cocotb's Icarus Verilog flow. Each target below
# builds and simulates exactly one RTL module against its cocotb test,
# and dumps a VCD waveform for that run into sim/waves/.
# ---------------------------------------------------------------------------

SIM           ?= icarus
TOPLEVEL_LANG ?= verilog

# Bit period used by the UART modules during simulation. The RTL defaults
# to 87 (a realistic divider for a real clock/baud pair), but tests override
# it to a small value so simulated UART frames finish quickly.
CLKS_PER_BIT  ?= 4

RTL_DIR    := $(CURDIR)/rtl
WAVES_DIR  := sim/waves

# Recursively expanded (=, not :=) so this only runs when a test target
# actually references it -- "make clean" has no Python/cocotb dependency
# and should not fail just because cocotb isn't on this shell's PATH.
COCOTB_MAKEFILES = $(shell python -m cocotb_tools.config --makefiles)

export PYTHONPATH := $(CURDIR)/tests

.PHONY: test test_fifo test_uart_tx test_uart_rx test_top clean

test: test_fifo test_uart_tx test_uart_rx test_top

# Runs a cocotb test against one top-level module and captures a VCD.
#   $(1) = short name, used for the build dir and the .vcd file name
#   $(2) = TOPLEVEL module name
#   $(3) = cocotb test module (python file under tests/, without .py)
#   $(4) = RTL source files required for this build
#   $(5) = extra compile-time flags, e.g. parameter overrides (optional)
#
# NOTE: the extra flags are passed to COMPILE_ARGS as a shell environment
# variable (COMPILE_ARGS="..." $(MAKE) ...), not as a "make VAR=val"
# command-line argument. A command-line argument would take fixed
# precedence for the rest of that sub-make run and block Makefile.icarus's
# own "COMPILE_ARGS +=" line that injects the +timescale plusarg, which
# would silently leave the simulator at its default 1-second precision.
# Keeping these flags out of EXTRA_ARGS also matters: EXTRA_ARGS is reused
# on the vvp *execution* command line too, and "-s iverilog_dump" would be
# misread there as a filename to run instead of a compile-time root module.
define run_cocotb_test
	@mkdir -p $(WAVES_DIR) sim_build/$(1)
	@echo 'module iverilog_dump();'                  >  sim_build/$(1)/dump.v
	@echo 'initial begin'                             >> sim_build/$(1)/dump.v
	@echo '    $$dumpfile("$(WAVES_DIR)/$(1).vcd");'  >> sim_build/$(1)/dump.v
	@echo '    $$dumpvars(0, $(2));'                  >> sim_build/$(1)/dump.v
	@echo 'end'                                        >> sim_build/$(1)/dump.v
	@echo 'endmodule'                                  >> sim_build/$(1)/dump.v
	COMPILE_ARGS="-s iverilog_dump $(5)" $(MAKE) -f $(COCOTB_MAKEFILES)/Makefile.sim \
		SIM=$(SIM) TOPLEVEL_LANG=$(TOPLEVEL_LANG) \
		SIM_BUILD=sim_build/$(1) \
		COCOTB_TOPLEVEL=$(2) COCOTB_TEST_MODULES=$(3) \
		VERILOG_SOURCES="$(4) sim_build/$(1)/dump.v"
endef

test_fifo:
	$(call run_cocotb_test,fifo,sync_fifo,test_fifo,$(RTL_DIR)/sync_fifo.sv,)

test_uart_tx:
	$(call run_cocotb_test,uart_tx,uart_tx,test_uart_tx,$(RTL_DIR)/uart_tx.sv,-Puart_tx.CLKS_PER_BIT=$(CLKS_PER_BIT))

test_uart_rx:
	$(call run_cocotb_test,uart_rx,uart_rx,test_uart_rx,$(RTL_DIR)/uart_rx.sv,-Puart_rx.CLKS_PER_BIT=$(CLKS_PER_BIT))

test_top:
	$(call run_cocotb_test,uart_mmio_top,uart_mmio_top,test_uart_mmio_top,$(RTL_DIR)/uart_tx.sv $(RTL_DIR)/uart_rx.sv $(RTL_DIR)/sync_fifo.sv $(RTL_DIR)/uart_mmio_top.sv,-Puart_mmio_top.CLKS_PER_BIT=$(CLKS_PER_BIT))

clean:
	bash scripts/clean.sh
