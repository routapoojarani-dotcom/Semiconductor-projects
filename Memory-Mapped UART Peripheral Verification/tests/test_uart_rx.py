"""cocotb tests for rtl/uart_rx.sv.

Covers reset behavior, single/multi-byte reception, framing-error
detection, and back-to-back frames.
"""

import cocotb
from cocotb.triggers import RisingEdge

from cocotb_helpers import reset_dut, send_uart_byte, settle, start_clock


async def wait_for_rx_done(dut, timeout_cycles=2000):
    """Wait until rx_done pulses high, then return with it still visible."""
    for _ in range(timeout_cycles):
        await RisingEdge(dut.clk)
        await settle()
        if dut.rx_done.value == 1:
            return
    assert False, "Timed out waiting for rx_done to pulse"


@cocotb.test()
async def test_reset_behavior(dut):
    """After reset, all status flags should be clear."""
    await start_clock(dut)
    dut.rx_serial.value = 1
    await reset_dut(dut)

    assert dut.rx_done.value == 0, "rx_done should be low after reset"
    assert dut.rx_busy.value == 0, "rx_busy should be low after reset"
    assert dut.framing_error.value == 0, "framing_error should be low after reset"


@cocotb.test()
async def test_receive_valid_byte(dut):
    """Receiving a well-formed frame for 0x55 should capture it correctly."""
    await start_clock(dut)
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)
    await send_uart_byte(dut, 0x55, clks_per_bit)
    await wait_for_rx_done(dut)

    assert dut.rx_data.value == 0x55, f"Expected rx_data to be 0x55, got 0x{int(dut.rx_data.value):02X}"
    assert dut.framing_error.value == 0, "A valid stop bit should not raise framing_error"


@cocotb.test()
async def test_receive_multiple_patterns(dut):
    """A range of data patterns should all be received correctly."""
    await start_clock(dut)
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)

    for byte in (0x00, 0xFF, 0xA5, 0x3C):
        await send_uart_byte(dut, byte, clks_per_bit)
        await wait_for_rx_done(dut)

        assert dut.rx_data.value == byte, f"Expected rx_data to be 0x{byte:02X}, got 0x{int(dut.rx_data.value):02X}"
        assert dut.framing_error.value == 0, f"Byte 0x{byte:02X} should not raise framing_error"

        await RisingEdge(dut.clk)


@cocotb.test()
async def test_framing_error(dut):
    """An invalid (low) stop bit should assert framing_error."""
    await start_clock(dut)
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)
    await send_uart_byte(dut, 0x3C, clks_per_bit, bad_stop_bit=True)
    await wait_for_rx_done(dut)

    assert dut.framing_error.value == 1, "An invalid stop bit should assert framing_error"


@cocotb.test()
async def test_back_to_back_receives(dut):
    """Multiple frames sent back-to-back should each be captured correctly."""
    await start_clock(dut)
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)
    bytes_to_send = [0x01, 0x23, 0x45, 0x67, 0x89]

    for byte in bytes_to_send:
        await send_uart_byte(dut, byte, clks_per_bit)
        await wait_for_rx_done(dut)
        assert dut.rx_data.value == byte, (
            f"Expected back-to-back byte 0x{byte:02X}, got 0x{int(dut.rx_data.value):02X}"
        )
