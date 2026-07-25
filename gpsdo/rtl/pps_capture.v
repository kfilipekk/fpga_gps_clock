//clk cycles between pps edges. the first edge only arms it
`default_nettype none

module pps_capture #(
    parameter W = 32
) (
    input  wire         clk,
    input  wire         pps,
    output wire         tick,
    output reg  [W-1:0] period,
    output reg          valid
);

    reg [2:0] sync = 3'b000;
    always @(posedge clk)
        sync <= {sync[1:0], pps};

    assign tick = sync[1] & ~sync[2];

    reg [W-1:0] counter = 0;
    reg [W-1:0] last    = 0;
    reg         armed   = 1'b0;

    initial begin
        period = 0;
        valid  = 1'b0;
    end

    always @(posedge clk) begin
        counter <= counter + 1'b1;
        valid   <= 1'b0;
        if (tick) begin
            last  <= counter;
            armed <= 1'b1;
            if (armed) begin
                period <= counter - last;  //wrap safe
                valid  <= 1'b1;
            end
        end
    end

endmodule
