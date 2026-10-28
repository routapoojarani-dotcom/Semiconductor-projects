// uart_tx.sv
//
// UART transmitter. Sends one byte per request as a standard 8-N-1 frame:
// 1 start bit (0), 8 data bits (LSB first), 1 stop bit (1). The line idles
// high, matching standard UART behavior.

module uart_tx #(
    parameter int CLKS_PER_BIT = 87  // clock cycles per UART bit period
)(
    input  logic       clk,
    input  logic       rst_n,

    input  logic        tx_start,
    input  logic [7:0]  tx_data,

    output logic        tx_serial,
    output logic        tx_busy,
    output logic        tx_done
);

    localparam int CNT_WIDTH = $clog2(CLKS_PER_BIT);

    typedef enum logic [1:0] {
        S_IDLE,
        S_START_BIT,
        S_DATA_BITS,
        S_STOP_BIT
    } state_t;

    state_t               state;
    logic [CNT_WIDTH-1:0] clk_count;
    logic [2:0]           bit_index;
    logic [7:0]           data_latch;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            clk_count  <= '0;
            bit_index  <= '0;
            data_latch <= '0;
            tx_serial  <= 1'b1;
            tx_busy    <= 1'b0;
            tx_done    <= 1'b0;
        end else begin
            tx_done <= 1'b0; // default: only pulses for one cycle, below

            case (state)
                // Idle: line held high, waiting for a request. A new
                // tx_start while already busy is implicitly ignored since
                // this branch is only reachable when the transmitter is
                // idle.
                S_IDLE: begin
                    tx_serial <= 1'b1;
                    clk_count <= '0;
                    bit_index <= '0;
                    tx_busy   <= 1'b0;

                    if (tx_start) begin
                        data_latch <= tx_data;
                        tx_busy    <= 1'b1;
                        tx_serial  <= 1'b0; // start bit
                        state      <= S_START_BIT;
                    end
                end

                S_START_BIT: begin
                    if (clk_count == CLKS_PER_BIT - 1) begin
                        clk_count <= '0;
                        tx_serial <= data_latch[0];
                        state     <= S_DATA_BITS;
                    end else begin
                        clk_count <= clk_count + 1'b1;
                    end
                end

                S_DATA_BITS: begin
                    if (clk_count == CLKS_PER_BIT - 1) begin
                        clk_count <= '0;
                        if (bit_index == 3'd7) begin
                            tx_serial <= 1'b1; // stop bit
                            state     <= S_STOP_BIT;
                        end else begin
                            bit_index <= bit_index + 1'b1;
                            tx_serial <= data_latch[bit_index + 1'b1];
                        end
                    end else begin
                        clk_count <= clk_count + 1'b1;
                    end
                end

                S_STOP_BIT: begin
                    if (clk_count == CLKS_PER_BIT - 1) begin
                        clk_count <= '0;
                        bit_index <= '0;
                        tx_busy   <= 1'b0;
                        tx_done   <= 1'b1;
                        state     <= S_IDLE;
                    end else begin
                        clk_count <= clk_count + 1'b1;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
