# Architecture

This project implements a small memory-mapped UART peripheral, built up
from four independent RTL blocks. Each block is verified on its own with
cocotb, and then all four are exercised together through the top-level
`uart_mmio_top` module.

## Block diagram

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
                             received byte + rx_done
```

`uart_tx` and `uart_rx` connect directly to the physical-looking
`tx_serial` / `rx_serial` lines. `uart_rx` does not connect straight to the
bus: every byte it receives is pushed into a `sync_fifo` instance, and
software drains that FIFO by reading the `RX_DATA` register. `uart_tx` is
driven directly by bus writes to `TX_DATA`; there is no TX FIFO in this
MVP (see [register_map.md](register_map.md)).

## uart_tx

A four-state shift-out state machine (`IDLE -> START_BIT -> DATA_BITS ->
STOP_BIT -> IDLE`). Each state holds `tx_serial` at the correct level for
`CLKS_PER_BIT` clock cycles: `0` for the start bit, each data bit LSB
first, then `1` for the stop bit. `tx_busy` is high for the whole frame;
`tx_done` pulses for exactly one clock cycle once the stop bit finishes. A
`tx_start` pulse arriving while the state machine is not in `IDLE` has no
effect, since only the `IDLE` state ever looks at `tx_start`.

## uart_rx

Mirrors `uart_tx`'s state machine, but samples the line instead of driving
it. `rx_serial` is first passed through a two-flop synchronizer
(`rx_sync_0` / `rx_sync_1`) since it is an asynchronous input from outside
the clock domain. From `IDLE`, a `0` on the synchronized line looks like a
start bit; `uart_rx` moves to `START_BIT` and re-checks the line at the
bit's midpoint to reject glitches. If it is still low, it proceeds to
`DATA_BITS` and samples each of the 8 bits at its midpoint, then checks the
stop bit in `STOP_BIT`. `rx_done` pulses for one cycle once a full frame
has been captured; `framing_error` is set on that same cycle if the stop
bit was not high.

## sync_fifo

A general-purpose synchronous FIFO used to buffer received bytes between
`uart_rx` and the bus. It tracks `wr_ptr`, `rd_ptr`, and an explicit
`count` register (rather than inferring full/empty purely from pointer
comparison), which makes `full` and `empty` simple equality checks against
`DEPTH` and `0`. Writes while full and reads while empty are both silently
ignored -- pointers and `count` simply do not move -- so neither can
corrupt existing data. A simultaneous read and write while full is treated
as a same-cycle "swap": the read frees a slot that the write is allowed to
use, so `count` stays at `DEPTH` instead of the write being dropped. See
the comments in `rtl/sync_fifo.sv` for the exact logic.

## uart_mmio_top

Instantiates `uart_tx`, `uart_rx`, and one `sync_fifo` (for received
bytes), and wires them to the four registers described in
[register_map.md](register_map.md). It also owns one small piece of state
that does not exist in the sub-modules: a latched `framing_error_latched`
flip-flop, set whenever `uart_rx` reports a framing error and only cleared
when software writes `CONTROL.clear_errors`. Without this latch, a later
good frame would silently clear the error before software could ever
observe it in `STATUS`.
