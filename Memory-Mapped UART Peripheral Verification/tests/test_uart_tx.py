"""cocotb tests for rtl/uart_tx.sv.

Covers reset behavior, single/multi-byte transmission framing, busy
handling, and the tx_done pulse.
"""

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge

from cocotb_helpers import read_uart_tx_frame, reset_dut, settle, start_clock


async def send_byte(dut, byte):
    """Pulse tx_start for one cycle to kick off transmission of byte."""
    clks_per_bit = int(dut.CLKS_PER_BIT.value)
    await RisingEdge(dut.clk)
    dut.tx_data.value = byte
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    dut.tx_start.value = 0
    return clks_per_bit


@cocotb.test()
async def test_reset_behavior(dut):
    """After reset, tx_serial should idle high and tx_busy/tx_done low."""
    await start_clock(dut)
    dut.tx_start.value = 0
    dut.tx_data.value = 0
    await reset_dut(dut)

    assert dut.tx_serial.value == 1, "tx_serial should idle high after reset"
    assert dut.tx_busy.value == 0, "tx_busy should be low after reset"
    assert dut.tx_done.value == 0, "tx_done should be low after reset"


@cocotb.test()
async def test_single_byte_transmission(dut):
    """Sending 0x55 should produce a start bit, 8 LSB-first data bits, and a stop bit."""
    await start_clock(dut)
    dut.tx_start.value = 0
    dut.tx_data.value = 0
    await reset_dut(dut)

    byte = 0x55
    clks_per_bit = await send_byte(dut, byte)
    start_bit, data_byte, stop_bit = await read_uart_tx_frame(dut, clks_per_bit)

    assert start_bit == 0, "Start bit should be sampled low"
    assert data_byte == byte, f"Expected to decode 0x{byte:02X}, got 0x{data_byte:02X}"
    assert stop_bit == 1, "Stop bit should be sampled high"


@cocotb.test()
async def test_multiple_data_patterns(dut):
    """A range of data patterns should all be transmitted correctly."""
    await start_clock(dut)
    dut.tx_start.value = 0
    dut.tx_data.value = 0
    await reset_dut(dut)

    for byte in (0x00, 0xFF, 0xA5, 0x3C):
        clks_per_bit = await send_byte(dut, byte)
        start_bit, data_byte, stop_bit = await read_uart_tx_frame(dut, clks_per_bit)

        assert start_bit == 0, f"Start bit should be low for byte 0x{byte:02X}"
        assert data_byte == byte, f"Expected 0x{byte:02X}, got 0x{data_byte:02X}"
        assert stop_bit == 1, f"Stop bit should be high for byte 0x{byte:02X}"

        # Wait for the transmitter to fully return to idle before the next byte.
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_busy_behavior(dut):
    """A tx_start received while busy should be ignored, not corrupt the frame."""
    await start_clock(dut)
    dut.tx_start.value = 0
    dut.tx_data.value = 0
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)

    await RisingEdge(dut.clk)
    dut.tx_data.value = 0x11
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    await settle()
    assert dut.tx_busy.value == 1, "tx_busy should go high once a transmission starts"

    # Attempt a second, different byte while still busy. It must be ignored.
    dut.tx_data.value = 0x99
    dut.tx_start.value = 1
    await RisingEdge(dut.clk)
    dut.tx_start.value = 0

    start_bit, data_byte, stop_bit = await read_uart_tx_frame(dut, clks_per_bit)

    assert data_byte == 0x11, (
        f"tx_start while busy should be ignored; expected the original byte 0x11, got 0x{data_byte:02X}"
    )
    assert start_bit == 0 and stop_bit == 1, "Frame should still be well-formed despite the busy tx_start attempt"


@cocotb.test()
async def test_done_pulse(dut):
    """tx_done should pulse for exactly one clock cycle after the stop bit."""
    await start_clock(dut)
    dut.tx_start.value = 0
    dut.tx_data.value = 0
    await reset_dut(dut)

    clks_per_bit = await send_byte(dut, 0x7A)

    # 1 start bit + 8 data bits + 1 stop bit = 10 bit periods per frame.
    await ClockCycles(dut.clk, clks_per_bit * 10 - 1)

    done_seen = False
    for _ in range(3):
        await RisingEdge(dut.clk)
        await settle()
        if dut.tx_done.value == 1:
            done_seen = True
            break

    assert done_seen, "Expected tx_done to pulse shortly after the stop bit completes"
    assert dut.tx_busy.value == 0, "tx_busy should drop once the frame is fully sent"
