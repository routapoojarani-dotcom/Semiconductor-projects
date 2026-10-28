# Verification Plan

This project is verified entirely with [cocotb](https://www.cocotb.org/)
testbenches running against [Icarus Verilog](http://iverilog.icarus.com/).
Each RTL module has its own test file that exercises it in isolation, and
`uart_mmio_top` is additionally verified as an integrated system.

## Simulation environment

- Simulator: Icarus Verilog (`SIM=icarus` in the Makefile; the default).
- Clock: a free-running 100 MHz clock (`CLK_PERIOD_NS = 10` in
  `tests/cocotb_helpers.py`) drives every testbench.
- Bit timing: the RTL defaults `CLKS_PER_BIT` to `87`, a realistic divider
  for a real clock/baud-rate pair. The Makefile overrides it to `4` for
  simulation (`CLKS_PER_BIT ?= 4`) so simulated UART frames finish in a
  reasonable number of cycles. Tests read the actual compiled-in value
  back from the DUT (`int(dut.CLKS_PER_BIT.value)`) rather than
  hardcoding it, so they stay correct if that override ever changes.

## Verification matrix

| Feature                                   | Test file                | Status  |
|--------------------------------------------|---------------------------|---------|
| FIFO reset behavior                        | `test_fifo.py`            | Covered |
| FIFO single write/read                     | `test_fifo.py`            | Covered |
| FIFO ordering (FIFO semantics)             | `test_fifo.py`            | Covered |
| FIFO full condition                        | `test_fifo.py`            | Covered |
| FIFO empty condition                       | `test_fifo.py`            | Covered |
| FIFO overflow protection                   | `test_fifo.py`            | Covered |
| FIFO underflow protection                  | `test_fifo.py`            | Covered |
| FIFO simultaneous read/write               | `test_fifo.py`            | Covered |
| UART TX reset behavior                     | `test_uart_tx.py`         | Covered |
| UART TX single-byte frame                  | `test_uart_tx.py`         | Covered |
| UART TX multiple data patterns             | `test_uart_tx.py`         | Covered |
| UART TX busy handling                      | `test_uart_tx.py`         | Covered |
| UART TX done pulse                         | `test_uart_tx.py`         | Covered |
| UART RX reset behavior                     | `test_uart_rx.py`         | Covered |
| UART RX valid frame                        | `test_uart_rx.py`         | Covered |
| UART RX multiple data patterns             | `test_uart_rx.py`         | Covered |
| UART RX framing error                      | `test_uart_rx.py`         | Covered |
| UART RX back-to-back frames                | `test_uart_rx.py`         | Covered |
| MMIO reset behavior                        | `test_uart_mmio_top.py`   | Covered |
| MMIO TX_DATA write -> real UART frame       | `test_uart_mmio_top.py`   | Covered |
| MMIO RX frame -> RX_DATA                    | `test_uart_mmio_top.py`   | Covered |
| MMIO STATUS bits (tx_busy/rx_data_available/framing_error) | `test_uart_mmio_top.py` | Covered |
| MMIO RX FIFO ordering through RX_DATA      | `test_uart_mmio_top.py`   | Covered |
| MMIO CONTROL.clear_errors                  | `test_uart_mmio_top.py`   | Covered |

## Test style

Every test file builds on a small set of shared async helpers in
`tests/cocotb_helpers.py`:

- `start_clock(dut)` / `reset_dut(dut)` -- common setup used by every test.
- `send_uart_byte(dut, byte, clks_per_bit)` -- bit-bangs one UART frame
  onto a serial input (used to drive `rx_serial` in the RX and top-level
  tests).
- `read_uart_tx_frame(dut, clks_per_bit)` -- waits for and decodes one UART
  frame from a serial output (used to check `tx_serial` in the TX and
  top-level tests).
- `mmio_write(dut, addr, data)` / `mmio_read(dut, addr)` -- drive a single
  register transaction on the `uart_mmio_top` bus.

Keeping these in one place means each test file only contains the logic
specific to what it is checking, and all four files exercise the DUT the
same way. Every assertion includes an explanation of what was expected and
what was actually observed, for example:

```python
assert value == 3, f"Expected FIFO count to be 3, got {value}"
```

## Waveforms

`make test_fifo`, `make test_uart_tx`, `make test_uart_rx`, and
`make test_top` each generate a VCD waveform under `sim/waves/` (see
[waveform_debugging.md](waveform_debugging.md)). The top-level system test
(`make test_top`) is the most useful one to look at, since it shows the
UART bus, both serial lines, and the RX FIFO all changing together.

## Known limitations

- There is no TX FIFO, so back-to-back `TX_DATA` writes while busy are
  dropped rather than queued (see [register_map.md](register_map.md)).
  This is a deliberate MVP scope decision, not a bug, and is listed as a
  possible future improvement in the main README.
- Coverage here means "this behavior has a directed test," not
  measured functional or code coverage. Adding coverage reporting is
  listed as a possible future improvement in the main README.
