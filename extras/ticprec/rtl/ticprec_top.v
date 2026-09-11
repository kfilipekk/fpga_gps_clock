//one ring edge into both tic channels
`default_nettype none

module ticprec_top #(
    parameter UART_DIV = 234,
    parameter TDC_N    = 1200,
    parameter RING_DIV = 13
) (
    input  wire       clk,
    output wire       uart_tx,
    output wire [5:0] led
);

    wire ring;
    ring_osc #(.DIV(RING_DIV)) u_ring (.clk(clk), .out(ring));

    wire ring_b;
`ifdef SYNTHESIS
    (* keep *) LUT1 #(.INIT(2'b10)) u_buf (.I0(ring), .F(ring_b));
`else
    assign ring_b = ring;
`endif

    wire [31:0] interval;
    wire [11:0] fine_a, fine_b;
    wire        valid;
    tic #(.N(TDC_N)) u_tic (
        .clk(clk), .a(ring), .b(ring_b), .interval(interval),
        .fine_a(fine_a), .fine_b(fine_b), .valid(valid)
    );

    function [7:0] hx(input [3:0] v);
        hx = (v < 4'd10) ? 8'h30 + {4'b0, v} : 8'h37 + {4'b0, v};
    endfunction

    //edges that arrive mid line are dropped
    reg [55:0] word = 0;
    reg [4:0]  idx  = 0;
    reg        busy = 1'b0;
    wire [4:0] k = idx - ((idx > 5'd12) ? 5'd2 : (idx > 5'd8) ? 5'd1 : 5'd0);
    wire [7:0] tx_byte = (idx == 5'd8 || idx == 5'd12) ? " "
                       : (idx == 5'd16)                 ? 8'h0A
                       :                                  hx(word[55 - 4 * k -: 4]);
    wire tx_ready;

    always @(posedge clk)
        if (!busy) begin
            if (valid) begin
                word <= {interval, fine_a, fine_b};
                idx  <= 0;
                busy <= 1'b1;
            end
        end else if (tx_ready) begin
            if (idx == 5'd16) busy <= 1'b0;
            idx <= idx + 1'b1;
        end

    uart_tx #(.DIV(UART_DIV)) u_tx (
        .clk(clk), .data(tx_byte), .valid(busy), .ready(tx_ready), .tx(uart_tx)
    );

    reg beat = 1'b0;
    always @(posedge clk)
        if (valid) beat <= ~beat;

    assign led = ~{beat, 5'b0};

endmodule
