"""Shared cocotb helper functions used by every test file in this suite.

Keeping these in one place avoids repeating the same reset, UART bit-banging,
and MMIO bus logic in each test file, and keeps the test files themselves
focused on what behavior they are checking.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

CLK_PERIOD_NS = 10  # 100 MHz simulation clock

# Small delay used after crossing a clock edge, before reading a signal that
# the DUT updates with a nonblocking assignment on that same edge. Icarus
# fires cocotb's RisingEdge callback before those updates are guaranteed to
# be visible, so reading immediately afterward can return the pre-edge
# value. A short real-time wait (instead of the ReadOnly() trigger) settles
# this without imposing "no writes right after" ordering rules on callers.
_SETTLE_NS = 1


async def settle():
    """Wait briefly so nonblocking register updates from the last clock
    edge become visible before the caller reads a signal."""
    await Timer(_SETTLE_NS, units="ns")


async def start_clock(dut):
    """Start a free-running clock on dut.clk."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, units="ns").start())


async def reset_dut(dut, cycles=5):
    """Drive the active-low reset for a few cycles, then release it."""
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, cycles)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await settle()


async def send_uart_byte(dut, byte, clks_per_bit, serial_signal_name="rx_serial", bad_stop_bit=False):
    """Bit-bang one UART frame (start bit, 8 data bits LSB-first, stop bit)
    onto the given serial signal of the DUT.

    Set bad_stop_bit=True to drive an invalid (low) stop bit, which is used
    to exercise framing-error detection.
    """
    serial = getattr(dut, serial_signal_name)

    serial.value = 0  # start bit
    await ClockCycles(dut.clk, clks_per_bit)

    for bit_index in range(8):
        serial.value = (byte >> bit_index) & 0x1
        await ClockCycles(dut.clk, clks_per_bit)

    serial.value = 0 if bad_stop_bit else 1  # stop bit
    await ClockCycles(dut.clk, clks_per_bit)


async def read_uart_tx_frame(dut, clks_per_bit, serial_signal_name="tx_serial"):
    """Wait for a UART frame on the given serial output and decode it.

    Returns a tuple of (start_bit, data_byte, stop_bit) sampled at the
    midpoint of each bit period, mirroring how a real UART receiver works.
    """
    serial = getattr(dut, serial_signal_name)

    # Let anything the caller just did settle before we start polling.
    await settle()

    # Wait for the line to fall, marking the start of a frame.
    while serial.value != 0:
        await RisingEdge(dut.clk)
        await settle()

    await ClockCycles(dut.clk, clks_per_bit // 2)
    await settle()
    start_bit = int(serial.value)

    # Advance to the midpoint of data bit 0.
    await ClockCycles(dut.clk, clks_per_bit)
    await settle()

    data_bits = []
    for _ in range(8):
        data_bits.append(int(serial.value))
        await ClockCycles(dut.clk, clks_per_bit)
        await settle()

    stop_bit = int(serial.value)

    data_byte = 0
    for bit_index, bit_value in enumerate(data_bits):
        data_byte |= bit_value << bit_index

    return start_bit, data_byte, stop_bit


async def mmio_write(dut, addr, data):
    """Perform one synchronous memory-mapped write transaction."""
    await RisingEdge(dut.clk)
    dut.bus_addr.value = addr
    dut.bus_wr_data.value = data
    dut.bus_wr_en.value = 1
    await RisingEdge(dut.clk)
    dut.bus_wr_en.value = 0
    await settle()


async def mmio_read(dut, addr):
    """Perform one synchronous memory-mapped read transaction.

    Returns the byte the DUT drove on bus_rd_data while the read was
    active.
    """
    await RisingEdge(dut.clk)
    dut.bus_addr.value = addr
    dut.bus_rd_en.value = 1
    await settle()
    value = int(dut.bus_rd_data.value)
    await RisingEdge(dut.clk)
    dut.bus_rd_en.value = 0
    await settle()
    return value
