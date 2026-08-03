//flips state once per press (active low), debounced over HOLD clocks
`default_nettype none

module btn_toggle #(
    parameter HOLD = 270000  //10 ms
) (
    input  wire clk,
    input  wire btn,
    output reg  state
);

    reg [1:0] sync   = 2'b11;
    reg       stable = 1'b1;
    reg [$clog2(HOLD)-1:0] cnt = 0;

    initial state = 1'b0;

    always @(posedge clk) begin
        sync <= {sync[0], btn};
        if (sync[1] == stable) begin
            cnt <= 0;
        end else if (cnt == HOLD - 1) begin
            cnt    <= 0;
            stable <= sync[1];
            if (!sync[1]) state <= ~state;
        end else begin
            cnt <= cnt + 1'b1;
        end
    end

endmodule
