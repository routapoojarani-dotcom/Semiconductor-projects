# Register Map

`uart_mmio_top` exposes the UART peripheral through four 8-bit registers on
a simple synchronous bus (`bus_wr_en`, `bus_rd_en`, `bus_addr[3:0]`,
`bus_wr_data[7:0]`, `bus_rd_data[7:0]`). Only addresses `0x0`-`0x3` are
implemented; reading or writing any other address returns `0x00` and has no
effect.

| Address | Name    | Access | Purpose                          |
|---------|---------|--------|-----------------------------------|
| `0x0`   | TX_DATA | W      | Queue a byte for transmission     |
| `0x1`   | RX_DATA | R      | Pop the oldest received byte      |
| `0x2`   | STATUS  | R      | Current peripheral status flags   |
| `0x3`   | CONTROL | R/W    | Error-clear command register      |

## 0x0 - TX_DATA (write-only)

Writing a byte to this address starts a UART transmission **if the
transmitter is idle** (`STATUS.tx_busy == 0`).

There is no TX FIFO in this MVP. If software writes to `TX_DATA` while
`tx_busy` is already `1`, the write is silently dropped -- the byte is
never queued and never transmitted. Software should poll `STATUS.tx_busy`
(or wait for `STATUS.tx_done`) before writing the next byte. Adding a TX
FIFO so back-to-back writes queue instead of being dropped is listed as a
future improvement in the main [README](../README.md).

Reading this address returns `0x00`.

## 0x1 - RX_DATA (read-only)

Reading this address pops and returns the oldest byte from the internal RX
FIFO (depth `FIFO_DEPTH`, 16 by default). Each byte the UART receiver
successfully captures is pushed into this FIFO automatically; software
does not need to do anything to receive bytes other than read them out.

Software should check `STATUS.rx_data_available` before reading. Reading
`RX_DATA` while the FIFO is empty does not corrupt anything (the FIFO's own
underflow protection applies, see [architecture.md](architecture.md)), but
the returned value is not meaningful.

Writing to this address has no effect.

## 0x2 - STATUS (read-only)

| Bit | Name               | Meaning                                            |
|-----|--------------------|-----------------------------------------------------|
| 0   | `tx_busy`          | A transmission is currently in progress             |
| 1   | `tx_done`          | `uart_tx`'s one-cycle done pulse, passed through     |
| 2   | `rx_data_available`| The RX FIFO is not empty (`RX_DATA` has a byte)      |
| 3   | `rx_fifo_full`      | The RX FIFO is full; new received bytes will be lost |
| 4   | `framing_error`    | A latched framing error is pending (see below)       |
| 7:5 | reserved           | Always read as `0`                                   |

`tx_done` (bit 1) is a direct pass-through of `uart_tx`'s internal
`tx_done` pulse, so it is only visible on the single clock cycle it fires.
It is included for completeness and for waveform inspection; software
should generally rely on `tx_busy` dropping back to `0` to know a
transmission finished, since that is a stable level rather than a pulse.

`framing_error` (bit 4) is **latched**, not a direct pass-through of
`uart_rx`'s `framing_error` output. `uart_rx` only asserts its
`framing_error` output for the frame it just finished, and a later good
frame would otherwise clear it before software ever had a chance to see
it. `uart_mmio_top` catches that pulse and holds `STATUS.framing_error`
high until software explicitly clears it (see `CONTROL` below).

## 0x3 - CONTROL (read/write)

| Bit | Name           | Meaning                                    |
|-----|----------------|----------------------------------------------|
| 0   | `clear_errors` | Write `1` to clear the latched framing error |
| 7:1 | reserved       | Ignored on write                              |

`CONTROL` is a self-clearing command register, not a stored value: writing
`1` to bit 0 clears `STATUS.framing_error` on that same clock cycle, and
reading `CONTROL` always returns `0x00`. There is nothing to "hold" in this
register -- it exists purely to carry the `clear_errors` command.
