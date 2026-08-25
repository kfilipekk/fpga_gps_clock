//8n1, DIV clocks per bit, samples mid bit
`default_nettype none

module uart_rx #(
    parameter DIV = 234  //115200 baud
) (
    input  wire       clk,
    input  wire       rx,
    output reg  [7:0] data = 8'd0,
    output reg        valid = 1'b0
);

    localparam W = $clog2(DIV);

    reg [3:0]        bits = 4'd0;
    reg [7:0]        sr   = 8'd0;
    reg [W-1:0]      baud = 0;
    reg              half = 1'b0;

    always @(posedge clk) begin
        valid <= 1'b0;
        if (bits == 0) begin
            if (!rx) begin
                bits <= 4'd1;
                baud <= 0;
                half <= 1'b1;
            end
        end else if (half ? (baud == DIV / 2 - 1) : (baud == DIV - 1)) begin
            baud <= 0;
            half <= 1'b0;
            if (bits == 4'd1) begin
                if (rx) bits <= 4'd0;       //false start
                else bits <= 4'd2;
            end else if (bits <= 4'd9) begin
                sr   <= {rx, sr[7:1]};
                bits <= bits + 4'd1;
            end else begin
                data  <= sr;
                valid <= 1'b1;
                bits  <= 4'd0;
            end
        end else begin
            baud <= baud + 1'b1;
        end
    end

endmodule
