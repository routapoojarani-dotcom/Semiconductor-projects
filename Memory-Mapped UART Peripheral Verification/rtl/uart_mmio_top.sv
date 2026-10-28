// uart_mmio_top.sv
//
// Top-level UART peripheral: wires uart_tx, uart_rx, and an RX FIFO behind
// a small memory-mapped register interface. See docs/register_map.md for
// the full register description.
//
// This MVP does not include a TX FIFO: a write to TX_DATA while the
// transmitter is busy is silently dropped (see docs/register_map.md).

module uart_mmio_top #(
    parameter int CLKS_PER_BIT = 87,
    parameter int FIFO_DEPTH   = 16
)(
    input  logic       clk,
    input  logic       rst_n,

    input  logic       bus_wr_en,
    input  logic       bus_rd_en,
    input  logic [3:0] bus_addr,
    input  logic [7:0] bus_wr_data,
    output logic [7:0] bus_rd_data,

    input  logic       rx_serial,
    output logic       tx_serial
);

    localparam logic [3:0] ADDR_TX_DATA = 4'h0;
    localparam logic [3:0] ADDR_RX_DATA = 4'h1;
    localparam logic [3:0] ADDR_STATUS  = 4'h2;
    localparam logic [3:0] ADDR_CONTROL = 4'h3;

    // -----------------------------------------------------------------
    // UART transmitter
    // -----------------------------------------------------------------
    logic tx_start;
    logic tx_busy;
    logic tx_done;

    // A write to TX_DATA only starts a transmission when the transmitter
    // is idle; a write that arrives while busy is dropped (no TX FIFO in
    // this MVP).
    assign tx_start = bus_wr_en && (bus_addr == ADDR_TX_DATA) && !tx_busy;

    uart_tx #(
        .CLKS_PER_BIT (CLKS_PER_BIT)
    ) u_uart_tx (
        .clk       (clk),
        .rst_n     (rst_n),
        .tx_start  (tx_start),
        .tx_data   (bus_wr_data),
        .tx_serial (tx_serial),
        .tx_busy   (tx_busy),
        .tx_done   (tx_done)
    );

    // -----------------------------------------------------------------
    // UART receiver
    // -----------------------------------------------------------------
    logic [7:0] rx_data;
    logic       rx_done;
    logic       rx_busy;
    logic       rx_framing_error;

    uart_rx #(
        .CLKS_PER_BIT (CLKS_PER_BIT)
    ) u_uart_rx (
        .clk           (clk),
        .rst_n         (rst_n),
        .rx_serial     (rx_serial),
        .rx_data       (rx_data),
        .rx_done       (rx_done),
        .rx_busy       (rx_busy),
        .framing_error (rx_framing_error)
    );

    // -----------------------------------------------------------------
    // RX FIFO: buffers received bytes until software reads RX_DATA.
    // -----------------------------------------------------------------
    logic       rx_fifo_rd_en;
    logic [7:0] rx_fifo_rd_data;
    logic       rx_fifo_full;
    logic       rx_fifo_empty;

    assign rx_fifo_rd_en = bus_rd_en && (bus_addr == ADDR_RX_DATA);

    sync_fifo #(
        .DATA_WIDTH (8),
        .DEPTH      (FIFO_DEPTH)
    ) u_rx_fifo (
        .clk     (clk),
        .rst_n   (rst_n),
        .wr_en   (rx_done),
        .wr_data (rx_data),
        .rd_en   (rx_fifo_rd_en),
        .rd_data (rx_fifo_rd_data),
        .full    (rx_fifo_full),
        .empty   (rx_fifo_empty),
        .count   ()
    );

    // -----------------------------------------------------------------
    // Sticky framing-error flag. uart_rx re-evaluates framing_error on
    // every frame, so without latching it here a later good frame would
    // silently clear the error before software ever saw STATUS. Software
    // clears it explicitly through CONTROL.clear_errors.
    // -----------------------------------------------------------------
    logic framing_error_latched;
    logic clear_errors;

    assign clear_errors = bus_wr_en && (bus_addr == ADDR_CONTROL) && bus_wr_data[0];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            framing_error_latched <= 1'b0;
        end else if (clear_errors) begin
            framing_error_latched <= 1'b0;
        end else if (rx_done && rx_framing_error) begin
            framing_error_latched <= 1'b1;
        end
    end

    // -----------------------------------------------------------------
    // Bus read mux
    // -----------------------------------------------------------------
    logic [7:0] status_reg;

    assign status_reg = {
        3'b000,                 // [7:5] reserved
        framing_error_latched,  // [4]
        rx_fifo_full,           // [3]
        !rx_fifo_empty,         // [2] rx_data_available
        tx_done,                // [1]
        tx_busy                 // [0]
    };

    always_comb begin
        case (bus_addr)
            ADDR_RX_DATA: bus_rd_data = rx_fifo_rd_data;
            ADDR_STATUS:  bus_rd_data = status_reg;
            ADDR_CONTROL: bus_rd_data = 8'h00; // self-clearing command register
            default:      bus_rd_data = 8'h00;
        endcase
    end

endmodule
