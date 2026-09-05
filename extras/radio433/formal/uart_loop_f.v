//uart_tx into uart_rx: every byte sent arrives once, unchanged
`default_nettype none

module uart_loop_f (
    input wire       clk,
    input wire [7:0] data,
    input wire       valid
);
    localparam DIV = 4;

    wire       ready, line, got;
    wire [7:0] rxd;
    uart_tx #(.DIV(DIV)) tx (
        .clk(clk), .data(data), .valid(valid), .ready(ready), .tx(line)
    );
    uart_rx #(.DIV(DIV)) rx (.clk(clk), .rx(line), .data(rxd), .valid(got));

    reg       pending   = 1'b0;
    reg       delivered = 1'b0;   //byte out, stop bit still going
    reg [7:0] sent      = 0;
    always @(posedge clk)
        if (valid && ready) begin
            pending   <= 1'b1;
            delivered <= 1'b0;
            sent      <= data;
        end else if (got) begin
            pending   <= 1'b0;
            delivered <= 1'b1;
        end

    always @* begin
        if (got) assert (pending && rxd == sent);
        if (pending) assert (!ready && !delivered);
        if (!ready)  assert (pending || delivered);
        cover (got);
    end
endmodule
