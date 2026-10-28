# FPGA Digital Systems Verification Lab

A small, fully open-source RTL verification project: a memory-mapped UART
peripheral, written in SystemVerilog and verified with Python
([cocotb](https://www.cocotb.org/)) testbenches running on
[Icarus Verilog](http://iverilog.icarus.com/). It's meant to demonstrate a
complete, real digital-design verification workflow -- RTL design,
testbench development, simulation, waveform debugging, and automated
regression testing -- at a scale that's still easy to read end to end.

## What this project does

It implements and verifies four RTL modules that together form a small
UART peripheral a CPU could talk to over a memory-mapped bus:

- `uart_tx` -- transmits one byte at a time as a standard 8-N-1 UART frame.
- `uart_rx` -- receives 8-N-1 frames and flags framing errors.
- `sync_fifo` -- a general-purpose synchronous FIFO, used to buffer
  received bytes.
- `uart_mmio_top` -- wires the above into four bus-visible registers
  (`TX_DATA`, `RX_DATA`, `STATUS`, `CONTROL`).

All four are verified with cocotb test suites (`tests/test_*.py`), and
`make test` runs the full suite against Icarus Verilog.

## Why UART, FIFO, MMIO, and cocotb

- **UART** is one of the simplest real serial protocols with meaningful
  timing behavior (start/stop bits, bit-period sampling), so it exercises
  genuine state-machine and timing verification without needing a complex
  bus protocol.
- **A FIFO** is included because almost every real peripheral needs to
  decouple two things running at different rates or on different
  schedules -- here, bytes arriving serially over time versus software
  reading them whenever it gets around to it.
- **A memory-mapped register interface** is how software actually talks to
  hardware peripherals in practice, so the project builds one (deliberately
  small, no AXI/Wishbone/APB) instead of stopping at the raw UART blocks.
- **cocotb** lets the testbenches be written in plain Python instead of
  more SystemVerilog, using regular `assert` statements, loops, and
  helper functions -- which keeps the test code approachable while still
  driving a real RTL simulator cycle-by-cycle.

## Architecture overview

```
                     +---------------------+
      bus_wr_data -->|                     |--> tx_serial
      bus_addr   --->|    uart_mmio_top    |
      bus_wr_en  --->|                     |<-- rx_serial
      bus_rd_en  --->|                     |
      bus_rd_data<---|                     |
                     +----------+----------+
                                |
                +---------------+----------------+
                |               |                |
           +----v----+    +-----v-----+     +----v-----+
           | uart_tx |    |  uart_rx  |      | sync_fifo|
           +---------+    +-----+-----+      | (RX FIFO)|
                                |             +----^-----+
                                +------------------+
```

See [docs/architecture.md](docs/architecture.md) for a full explanation of
each block, and [docs/register_map.md](docs/register_map.md) for the
register-level details.

## Repository structure

```
fpga-digital-systems-verification-lab/
├── README.md
├── Makefile
├── requirements.txt
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── verification_plan.md
│   ├── waveform_debugging.md
│   └── register_map.md
├── rtl/
│   ├── uart_tx.sv
│   ├── uart_rx.sv
│   ├── sync_fifo.sv
│   └── uart_mmio_top.sv
├── tests/
│   ├── cocotb_helpers.py
│   ├── test_uart_tx.py
│   ├── test_uart_rx.py
│   ├── test_fifo.py
│   └── test_uart_mmio_top.py
├── sim/
│   └── waves/        (generated .vcd waveforms land here)
└── scripts/
    └── clean.sh
```

## Setup instructions

You need three things: Python 3.8+, Icarus Verilog, and (optionally, for
viewing waveforms) GTKWave.

**Icarus Verilog + GTKWave:**

- Ubuntu/Debian: `sudo apt install iverilog gtkwave`
- macOS (Homebrew): `brew install icarus-verilog gtkwave`
- Windows: `winget install Icarus.Verilog` (bundles GTKWave), or download
  an installer from [bleyer.org/icarus](https://bleyer.org/icarus/)

Verify with `iverilog -V` and `vvp -V`.

**Python dependencies:**

```bash
pip install -r requirements.txt
```

A virtual environment is recommended (`python -m venv .venv`, then
activate it) so the packages below don't clash with anything else on your
system.

> **Windows note:** cocotb had not yet published wheels for Python 3.13+
> at the time this project was built, and some Python 3.10/3.11 `venv`
> setups on Windows can hit a `cocotb`/Icarus embedding quirk (a
> `ModuleNotFoundError: No module named 'pygpi'`, preceded by an
> `Unexpected sys.executable value` message). If you hit that, installing
> `cocotb`/`pytest` into your regular (non-venv) Python environment
> resolves it. This is a Windows-specific `venv` + native-extension
> embedding issue, not a bug in this project's RTL or tests.

## Running all tests

```bash
make test
```

This runs all four cocotb test suites (FIFO, UART TX, UART RX, and the
top-level MMIO integration) against Icarus Verilog and reports pass/fail
for every test case.

## Running individual tests

```bash
make test_fifo      # rtl/sync_fifo.sv
make test_uart_tx   # rtl/uart_tx.sv
make test_uart_rx   # rtl/uart_rx.sv
make test_top       # rtl/uart_mmio_top.sv (full integration)
```

## Viewing waveforms

Every target above writes a VCD file to `sim/waves/`:

```bash
gtkwave sim/waves/uart_tx.vcd
```

See [docs/waveform_debugging.md](docs/waveform_debugging.md) for what to
look for once it's open.

To remove all generated build/waveform artifacts:

```bash
make clean
```

## Current project status

All four RTL modules are implemented and passing their full cocotb test
suites (24 test cases total: 8 FIFO, 5 UART TX, 5 UART RX, 6 top-level
integration). There is no TX FIFO in this version -- see
[docs/register_map.md](docs/register_map.md) for what that means for
software writing to `TX_DATA`. Nothing here has been synthesized onto
physical FPGA hardware; this project is simulation-only.

## Future improvements

- Add a TX FIFO so back-to-back `TX_DATA` writes queue instead of being
  dropped while the transmitter is busy.
- Add an interrupt output signal (e.g. on `rx_data_available` or
  `framing_error`).
- Add parity bit support and/or a configurable baud-rate divisor register.
- Add Verilator as a second supported simulator alongside Icarus Verilog.
- Add a GitHub Actions workflow that runs `make test` on every push.
- Add randomized (rather than purely directed) cocotb tests for longer
  UART traffic streams.
- Add a small script that decodes UART frames directly from a `.vcd` file,
  independent of the live simulation.
