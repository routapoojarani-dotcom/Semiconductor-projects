"""cocotb tests for rtl/sync_fifo.sv.

Covers reset behavior, FIFO ordering, full/empty flags, overflow/underflow
protection, and simultaneous read/write handling.
"""

import cocotb
from cocotb.triggers import RisingEdge

from cocotb_helpers import reset_dut, settle, start_clock

FIFO_DEPTH = 16


async def fifo_write(dut, data):
    """Pulse a single write transaction into the FIFO for one clock cycle.

    Settles after the write edge before returning, so callers can
    immediately inspect count/full/empty without racing the DUT's
    nonblocking register updates for that edge.
    """
    dut.wr_data.value = data
    dut.wr_en.value = 1
    await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    await settle()


async def fifo_read(dut):
    """Pulse a single read transaction and return the byte that was on
    rd_data at the time the read was issued.
    """
    dut.rd_en.value = 1
    value = int(dut.rd_data.value)
    await RisingEdge(dut.clk)
    dut.rd_en.value = 0
    await settle()
    return value


@cocotb.test()
async def test_reset_behavior(dut):
    """After reset, the FIFO should be empty, not full, and count == 0."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    assert dut.empty.value == 1, "FIFO should be empty immediately after reset"
    assert dut.full.value == 0, "FIFO should not be full immediately after reset"
    assert dut.count.value == 0, f"Expected count to be 0 after reset, got {int(dut.count.value)}"


@cocotb.test()
async def test_single_write_and_read(dut):
    """A single byte written should come back out unchanged."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    await fifo_write(dut, 0x42)
    assert dut.count.value == 1, f"Expected count to be 1 after one write, got {int(dut.count.value)}"
    assert dut.empty.value == 0, "FIFO should not be empty after a write"

    value = await fifo_read(dut)
    assert value == 0x42, f"Expected to read back 0x42, got 0x{value:02X}"
    assert dut.count.value == 0, f"Expected count to be 0 after the read, got {int(dut.count.value)}"
    assert dut.empty.value == 1, "FIFO should be empty after draining the single entry"


@cocotb.test()
async def test_fifo_ordering(dut):
    """Bytes should be read back in the same order they were written (FIFO)."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    written = [0x11, 0x22, 0x33, 0x44, 0x55]
    for byte in written:
        await fifo_write(dut, byte)

    assert dut.count.value == len(written), (
        f"Expected count to be {len(written)} after writes, got {int(dut.count.value)}"
    )

    for expected in written:
        actual = await fifo_read(dut)
        assert actual == expected, f"Expected FIFO order to yield 0x{expected:02X}, got 0x{actual:02X}"


@cocotb.test()
async def test_full_condition(dut):
    """Writing DEPTH bytes should raise the full flag."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    for i in range(FIFO_DEPTH):
        await fifo_write(dut, i)

    assert dut.full.value == 1, "FIFO should report full after writing DEPTH entries"
    assert dut.count.value == FIFO_DEPTH, (
        f"Expected count to equal DEPTH ({FIFO_DEPTH}) when full, got {int(dut.count.value)}"
    )


@cocotb.test()
async def test_empty_condition(dut):
    """Draining a full FIFO should raise the empty flag."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    for i in range(FIFO_DEPTH):
        await fifo_write(dut, i)

    for _ in range(FIFO_DEPTH):
        await fifo_read(dut)

    assert dut.empty.value == 1, "FIFO should report empty after draining all entries"
    assert dut.count.value == 0, f"Expected count to be 0 after draining, got {int(dut.count.value)}"


@cocotb.test()
async def test_overflow_protection(dut):
    """Writing while full must not corrupt existing data or the count."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    for i in range(FIFO_DEPTH):
        await fifo_write(dut, 0xA0 + i)

    # Attempt an extra write while full; it should be dropped.
    await fifo_write(dut, 0xFF)

    assert dut.full.value == 1, "FIFO should remain full after an overflow attempt"
    assert dut.count.value == FIFO_DEPTH, (
        f"Expected count to stay at DEPTH ({FIFO_DEPTH}) after overflow attempt, got {int(dut.count.value)}"
    )

    # The original data should be intact and in order.
    for expected in range(FIFO_DEPTH):
        actual = await fifo_read(dut)
        assert actual == 0xA0 + expected, (
            f"Overflow attempt corrupted FIFO contents: expected 0x{0xA0 + expected:02X}, got 0x{actual:02X}"
        )


@cocotb.test()
async def test_underflow_protection(dut):
    """Reading while empty must not crash or corrupt FIFO state."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    await fifo_read(dut)  # attempt a read while empty

    assert dut.empty.value == 1, "FIFO should remain empty after an underflow attempt"
    assert dut.count.value == 0, f"Expected count to stay at 0 after underflow attempt, got {int(dut.count.value)}"

    # The FIFO should still work normally afterward.
    await fifo_write(dut, 0x7A)
    value = await fifo_read(dut)
    assert value == 0x7A, f"FIFO did not recover cleanly after underflow attempt, got 0x{value:02X}"


@cocotb.test()
async def test_simultaneous_read_write(dut):
    """A read and write on the same cycle should both take effect cleanly."""
    await start_clock(dut)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    await reset_dut(dut)

    await fifo_write(dut, 0x01)

    # Issue a simultaneous write and read.
    dut.wr_data.value = 0x02
    dut.wr_en.value = 1
    dut.rd_en.value = 1
    read_value = int(dut.rd_data.value)
    await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    await settle()

    assert read_value == 0x01, f"Expected simultaneous read to return the oldest byte 0x01, got 0x{read_value:02X}"
    assert dut.count.value == 1, (
        f"Expected count to stay at 1 after a simultaneous read+write, got {int(dut.count.value)}"
    )

    remaining = await fifo_read(dut)
    assert remaining == 0x02, f"Expected the byte written during the simultaneous cycle to remain, got 0x{remaining:02X}"
