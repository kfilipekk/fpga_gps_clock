//8n1, DIV clocks per bit
`default_nettype none

module uart_tx #(
    parameter DIV = 234  //115200 baud
) (
    input  wire       clk,
    input  wire [7:0] data,
    input  wire       valid,
    output wire       ready,
    output wire       tx
);

    reg [9:0] shift = 10'h3FF;
    reg [3:0] bits  = 4'd0;
    reg [$clog2(DIV)-1:0] baud = 0;

    assign tx    = shift[0];
    assign ready = bits == 0;

    always @(posedge clk) begin
        if (bits == 0) begin
            if (valid) begin
                shift <= {1'b1, data, 1'b0};
                bits  <= 4'd10;
                baud  <= 0;
            end
        end else if (baud == DIV - 1) begin
            baud  <= 0;
            shift <= {1'b1, shift[9:1]};
            bits  <= bits - 4'd1;
        end else begin
            baud <= baud + 1'b1;
        end
    end

endmodule
