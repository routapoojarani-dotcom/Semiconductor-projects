// sync_fifo.sv
//
// A simple synchronous FIFO (first-in, first-out) buffer. Used inside
// uart_mmio_top.sv to hold received UART bytes until software reads them
// through the memory-mapped RX_DATA register.

module sync_fifo #(
    parameter int DATA_WIDTH = 8,
    parameter int DEPTH      = 16
)(
    input  logic                       clk,
    input  logic                       rst_n,

    input  logic                       wr_en,
    input  logic [DATA_WIDTH-1:0]      wr_data,

    input  logic                       rd_en,
    output logic [DATA_WIDTH-1:0]      rd_data,

    output logic                       full,
    output logic                       empty,
    output logic [$clog2(DEPTH+1)-1:0] count
);

    localparam int PTR_WIDTH = (DEPTH > 1) ? $clog2(DEPTH) : 1;

    logic [DATA_WIDTH-1:0]      mem [0:DEPTH-1];
    logic [PTR_WIDTH-1:0]       wr_ptr;
    logic [PTR_WIDTH-1:0]       rd_ptr;
    logic [$clog2(DEPTH+1)-1:0] count_r;

    assign full   = (count_r == DEPTH);
    assign empty  = (count_r == 0);
    assign count  = count_r;
    assign rd_data = mem[rd_ptr];

    // A normal write is only accepted when there is room. If the FIFO is
    // already full, a write is still allowed *only* when it is paired with
    // a read in the same cycle, since that read frees a slot in the same
    // clock edge. This keeps a simultaneous read/write clean (no data
    // corruption) instead of silently dropping the write.
    logic do_read;
    logic do_write;

    assign do_read  = rd_en && !empty;
    assign do_write = wr_en && (!full || do_read);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr  <= '0;
            rd_ptr  <= '0;
            count_r <= '0;
        end else begin
            if (do_write) begin
                mem[wr_ptr] <= wr_data;
                wr_ptr      <= (wr_ptr == DEPTH-1) ? '0 : wr_ptr + 1'b1;
            end

            if (do_read) begin
                rd_ptr <= (rd_ptr == DEPTH-1) ? '0 : rd_ptr + 1'b1;
            end

            case ({do_write, do_read})
                2'b10:   count_r <= count_r + 1'b1;
                2'b01:   count_r <= count_r - 1'b1;
                default: count_r <= count_r; // 2'b00 or 2'b11: no net change
            endcase
        end
    end

endmodule
