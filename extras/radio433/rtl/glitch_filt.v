//a level has to hold for K clocks before it passes
`default_nettype none

module glitch_filt #(
    parameter CW = 16,
    parameter [CW-1:0] K = 4000
) (
    input  wire clk,
    input  wire din,
    output reg  out = 1'b0
);

    reg [1:0] s = 0;
    always @(posedge clk) s <= {s[0], din};

    reg [CW-1:0] cnt = 0;
    always @(posedge clk)
        if (s[1] == out)      cnt <= 0;
        else if (cnt == K)    begin out <= s[1]; cnt <= 0; end
        else                  cnt <= cnt + 1'b1;

endmodule
