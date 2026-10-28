// uart_rx.sv
//
// UART receiver. Detects a start bit, samples each bit near the middle of
// its period, and captures one 8-N-1 frame (LSB first). Flags a framing
// error if the stop bit is not high.

module uart_rx #(
    parameter int CLKS_PER_BIT = 87  // clock cycles per UART bit period
)(
    input  logic       clk,
    input  logic       rst_n,

    input  logic       rx_serial,

    output logic [7:0] rx_data,
    output logic       rx_done,
    output logic       rx_busy,
    output logic       framing_error
);

    localparam int CNT_WIDTH = $clog2(CLKS_PER_BIT);
    localparam int HALF_BIT  = CLKS_PER_BIT / 2;

    // Two-flop synchronizer so the asynchronous serial input cannot cause
    // metastability inside the receive state machine.
    logic rx_sync_0, rx_sync_1;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_sync_0 <= 1'b1;
            rx_sync_1 <= 1'b1;
        end else begin
            rx_sync_0 <= rx_serial;
            rx_sync_1 <= rx_sync_0;
        end
    end

    typedef enum logic [1:0] {
        S_IDLE,
        S_START_BIT,
        S_DATA_BITS,
        S_STOP_BIT
    } state_t;

    state_t               state;
    logic [CNT_WIDTH-1:0] clk_count;
    logic [2:0]           bit_index;
    logic [7:0]           data_shift;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            clk_count     <= '0;
            bit_index     <= '0;
            data_shift    <= '0;
            rx_data       <= '0;
            rx_done       <= 1'b0;
            rx_busy       <= 1'b0;
            framing_error <= 1'b0;
        end else begin
            rx_done <= 1'b0; // default: only pulses for one cycle, below

            case (state)
                S_IDLE: begin
                    clk_count <= '0;
                    bit_index <= '0;
                    if (rx_sync_1 == 1'b0) begin
                        // Falling edge on the synchronized line: candidate
                        // start bit.
                        rx_busy <= 1'b1;
                        state   <= S_START_BIT;
                    end else begin
                        rx_busy <= 1'b0;
                    end
                end

                S_START_BIT: begin
                    if (clk_count == HALF_BIT[CNT_WIDTH-1:0]) begin
                        if (rx_sync_1 == 1'b0) begin
                            // Confirmed low at the midpoint: real start bit.
                            clk_count <= '0;
                            state     <= S_DATA_BITS;
                        end else begin
                            // Line already went back high: treat as noise,
                            // not a real frame.
                            rx_busy <= 1'b0;
                            state   <= S_IDLE;
                        end
                    end else begin
                        clk_count <= clk_count + 1'b1;
                    end
                end

                S_DATA_BITS: begin
                    if (clk_count == CLKS_PER_BIT - 1) begin
                        clk_count             <= '0;
                        data_shift[bit_index] <= rx_sync_1;
                        if (bit_index == 3'd7) begin
                            state <= S_STOP_BIT;
                        end else begin
                            bit_index <= bit_index + 1'b1;
                        end
                    end else begin
                        clk_count <= clk_count + 1'b1;
                    end
                end

                S_STOP_BIT: begin
                    if (clk_count == CLKS_PER_BIT - 1) begin
                        rx_data       <= data_shift;
                        rx_done       <= 1'b1;
                        rx_busy       <= 1'b0;
                        framing_error <= ~rx_sync_1; // stop bit should read high
                        clk_count     <= '0;
                        bit_index     <= '0;
                        state         <= S_IDLE;
                    end else begin
                        clk_count <= clk_count + 1'b1;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
