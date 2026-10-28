"""cocotb tests for rtl/uart_mmio_top.sv.

Exercises the full peripheral through its memory-mapped register
interface: TX_DATA writes producing real UART frames, RX frames landing in
RX_DATA through the RX FIFO, STATUS bits, and CONTROL.clear_errors.
"""

import cocotb
from cocotb.triggers import ClockCycles

from cocotb_helpers import (
    mmio_read,
    mmio_write,
    read_uart_tx_frame,
    reset_dut,
    send_uart_byte,
    start_clock,
)

ADDR_TX_DATA = 0x0
ADDR_RX_DATA = 0x1
ADDR_STATUS = 0x2
ADDR_CONTROL = 0x3

STATUS_TX_BUSY = 1 << 0
STATUS_TX_DONE = 1 << 1
STATUS_RX_DATA_AVAILABLE = 1 << 2
STATUS_RX_FIFO_FULL = 1 << 3
STATUS_FRAMING_ERROR = 1 << 4

CONTROL_CLEAR_ERRORS = 1 << 0


async def wait_for_status_bit(dut, bit_mask, timeout_cycles=2000):
    """Poll STATUS until the given bit(s) are set, or fail on timeout."""
    for _ in range(timeout_cycles):
        status = await mmio_read(dut, ADDR_STATUS)
        if status & bit_mask:
            return status
        await ClockCycles(dut.clk, 1)
    assert False, f"Timed out waiting for STATUS bit(s) 0x{bit_mask:02X} to be set"


@cocotb.test()
async def test_reset_behavior(dut):
    """After reset, the line should idle high and STATUS should be quiet."""
    await start_clock(dut)
    dut.bus_wr_en.value = 0
    dut.bus_rd_en.value = 0
    dut.bus_addr.value = 0
    dut.bus_wr_data.value = 0
    dut.rx_serial.value = 1
    await reset_dut(dut)

    assert dut.tx_serial.value == 1, "tx_serial should idle high after reset"

    status = await mmio_read(dut, ADDR_STATUS)
    assert status == 0, f"Expected STATUS to be 0 immediately after reset, got 0x{status:02X}"


@cocotb.test()
async def test_tx_data_write_produces_uart_frame(dut):
    """Writing TX_DATA should transmit the byte as a real UART frame."""
    await start_clock(dut)
    dut.bus_wr_en.value = 0
    dut.bus_rd_en.value = 0
    dut.bus_addr.value = 0
    dut.bus_wr_data.value = 0
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)

    await mmio_write(dut, ADDR_TX_DATA, 0x5A)
    start_bit, data_byte, stop_bit = await read_uart_tx_frame(dut, clks_per_bit)

    assert start_bit == 0, "Start bit should be low"
    assert data_byte == 0x5A, f"Expected TX_DATA write to transmit 0x5A, got 0x{data_byte:02X}"
    assert stop_bit == 1, "Stop bit should be high"


@cocotb.test()
async def test_rx_frame_appears_in_rx_data(dut):
    """A serial frame received on rx_serial should be readable via RX_DATA."""
    await start_clock(dut)
    dut.bus_wr_en.value = 0
    dut.bus_rd_en.value = 0
    dut.bus_addr.value = 0
    dut.bus_wr_data.value = 0
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)

    await send_uart_byte(dut, 0x66, clks_per_bit)
    await wait_for_status_bit(dut, STATUS_RX_DATA_AVAILABLE)

    value = await mmio_read(dut, ADDR_RX_DATA)
    assert value == 0x66, f"Expected RX_DATA to return 0x66, got 0x{value:02X}"


@cocotb.test()
async def test_status_bits(dut):
    """STATUS should reflect tx_busy, rx_data_available, and framing_error."""
    await start_clock(dut)
    dut.bus_wr_en.value = 0
    dut.bus_rd_en.value = 0
    dut.bus_addr.value = 0
    dut.bus_wr_data.value = 0
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)

    # tx_busy should go high right after a TX_DATA write.
    await mmio_write(dut, ADDR_TX_DATA, 0x11)
    status = await mmio_read(dut, ADDR_STATUS)
    assert status & STATUS_TX_BUSY, "STATUS.tx_busy should be set while a transmission is in progress"

    # Let that transmission finish before moving on to the RX checks.
    await ClockCycles(dut.clk, clks_per_bit * 10 + 5)

    # rx_data_available should go high once a byte has been received.
    await send_uart_byte(dut, 0x22, clks_per_bit)
    status = await wait_for_status_bit(dut, STATUS_RX_DATA_AVAILABLE)
    assert status & STATUS_RX_DATA_AVAILABLE, "STATUS.rx_data_available should be set once a byte is received"

    # framing_error should go high after a bad stop bit.
    await send_uart_byte(dut, 0x33, clks_per_bit, bad_stop_bit=True)
    status = await wait_for_status_bit(dut, STATUS_FRAMING_ERROR)
    assert status & STATUS_FRAMING_ERROR, "STATUS.framing_error should be set after an invalid stop bit"


@cocotb.test()
async def test_rx_fifo_behavior(dut):
    """Multiple received bytes should queue up and be read back in order."""
    await start_clock(dut)
    dut.bus_wr_en.value = 0
    dut.bus_rd_en.value = 0
    dut.bus_addr.value = 0
    dut.bus_wr_data.value = 0
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)
    bytes_to_send = [0xAA, 0xBB, 0xCC]

    for byte in bytes_to_send:
        await send_uart_byte(dut, byte, clks_per_bit)
        await wait_for_status_bit(dut, STATUS_RX_DATA_AVAILABLE)

    for expected in bytes_to_send:
        value = await mmio_read(dut, ADDR_RX_DATA)
        assert value == expected, f"Expected RX FIFO order to yield 0x{expected:02X}, got 0x{value:02X}"


@cocotb.test()
async def test_error_clearing(dut):
    """CONTROL.clear_errors should clear a latched framing_error."""
    await start_clock(dut)
    dut.bus_wr_en.value = 0
    dut.bus_rd_en.value = 0
    dut.bus_addr.value = 0
    dut.bus_wr_data.value = 0
    dut.rx_serial.value = 1
    await reset_dut(dut)

    clks_per_bit = int(dut.CLKS_PER_BIT.value)

    await send_uart_byte(dut, 0x44, clks_per_bit, bad_stop_bit=True)
    status = await wait_for_status_bit(dut, STATUS_FRAMING_ERROR)
    assert status & STATUS_FRAMING_ERROR, "framing_error should be latched after a bad stop bit"

    await mmio_write(dut, ADDR_CONTROL, CONTROL_CLEAR_ERRORS)

    status = await mmio_read(dut, ADDR_STATUS)
    assert not (status & STATUS_FRAMING_ERROR), "CONTROL.clear_errors should clear the latched framing_error"
