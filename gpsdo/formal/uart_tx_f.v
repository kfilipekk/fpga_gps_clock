//reference model
`default_nettype none

module uart_tx_f (
    input wire       clk,
    input wire [7:0] data,
    input wire       valid
);
    localparam DIV = 4;

    wire ready, tx;
    uart_tx #(.DIV(DIV)) dut (
        .clk(clk), .data(data), .valid(valid), .ready(ready), .tx(tx)
    );

    reg       busy = 1'b0;
    reg [7:0] d    = 0;
    reg [5:0] t    = 0;
    always @(posedge clk)
        if (!busy) begin
            if (valid && ready) begin
                busy <= 1'b1;
                d    <= data;
                t    <= 0;
            end
        end else begin
            t <= t + 1'b1;
            if (t == 10 * DIV - 1) busy <= 1'b0;
        end

    wire [3:0] slot = t / DIV;   //0 start, 1-8 data, 9 stop

    always @* begin
        assert (ready == !busy);
        if (busy) begin
            assert (t < 10 * DIV);
            if (slot == 0)      assert (tx == 1'b0);
            else if (slot <= 8) assert (tx == d[slot - 1]);
            else                assert (tx == 1'b1);
        end else
            assert (tx == 1'b1);
        cover (busy && t == 10 * DIV - 1);
    end
endmodule
