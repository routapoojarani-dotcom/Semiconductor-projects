# Waveform Debugging

Every `make test_*` target dumps a VCD waveform to `sim/waves/`, named
after the target: `fifo.vcd`, `uart_tx.vcd`, `uart_rx.vcd`, and
`uart_mmio_top.vcd`. Open any of them with
[GTKWave](http://gtkwave.sourceforge.net/):

```bash
gtkwave sim/waves/uart_tx.vcd
```

Add the signals you want from the "SST" hierarchy panel on the left (the
top-level module name, e.g. `uart_tx`, then drag its signals into the wave
view). The sections below describe what to look for in each waveform.

## Confirming a UART frame (uart_tx.vcd / uart_rx.vcd)

Add `clk`, `tx_serial` (or `rx_serial`), `tx_busy`, `tx_done` (or
`rx_busy`, `rx_done`, `framing_error`). A correctly-formed frame looks
like this on the serial line, each segment `CLKS_PER_BIT` clocks wide:

```
idle (1) | start (0) | d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | stop (1) | idle (1)
```

- The line should be high at idle, drop to `0` for exactly one bit period
  (the start bit), then show 8 data bit periods LSB first, then return to
  `1` for the stop bit.
- `tx_busy` (or `rx_busy`) should be high for the entire frame -- from the
  start bit through the stop bit -- and low everywhere else.
- `tx_done` (or `rx_done`) should be a single-cycle pulse right after the
  stop bit period ends.
- If you deliberately corrupt the stop bit (see `test_framing_error` in
  `tests/test_uart_rx.py`), `framing_error` should pulse high on the same
  cycle as `rx_done`.

## Inspecting the FIFO (fifo.vcd)

Add `clk`, `wr_en`, `wr_data`, `rd_en`, `rd_data`, `full`, `empty`,
`count`. `count` is the easiest signal to eyeball: it should increment by
one on every cycle where `wr_en` is high and the FIFO isn't full, decrement
by one whenever `rd_en` is high and the FIFO isn't empty, and stay put
during a simultaneous read+write. `full` should go high exactly when
`count` reaches `DEPTH` (16 by default), and `empty` exactly when `count`
is `0`.

## Inspecting MMIO reads and writes (uart_mmio_top.vcd)

Add `clk`, `bus_addr`, `bus_wr_en`, `bus_wr_data`, `bus_rd_en`,
`bus_rd_data`, plus `tx_serial` and `rx_serial`. A write transaction shows
up as `bus_wr_en` high for one cycle with `bus_addr`/`bus_wr_data` already
stable; a read shows up the same way with `bus_rd_en` high and
`bus_rd_data` valid during that cycle. Watching `bus_addr == 0x0`
(`TX_DATA`) line up with a `tx_serial` start bit shortly afterward is a
good way to confirm the write path end-to-end. Likewise, a `rx_serial`
frame followed by a `bus_addr == 0x1` (`RX_DATA`) read returning the same
byte confirms the receive path through the FIFO.

## Common failure cases to look for

- **Off-by-one bit sampling**: if decoded data looks shifted or
  consistently wrong, zoom in on a single bit period and check that
  `uart_rx` is sampling at the *middle* of the period, not right at an
  edge.
- **`tx_busy`/`rx_busy` never dropping**: usually means the state machine
  got stuck waiting for a bit-period counter that never reached its
  target -- check `CLKS_PER_BIT` matches what the testbench expects.
- **`count` in `sync_fifo` drifting instead of stabilizing at `DEPTH` or
  `0`**: check for a write or read being accepted when it should have
  been blocked (i.e. `full`/`empty` not gating `wr_en`/`rd_en` as
  expected).
- **`STATUS.framing_error` clearing itself**: this would mean the latch in
  `uart_mmio_top` is missing or wired to the wrong signal --
  `framing_error` from `uart_rx` itself is not latched and will drop on
  the next good frame.
