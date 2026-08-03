//first order sigma delta
`default_nettype none

module sd_dac #(
    parameter W = 16
) (
    input  wire         clk,
    input  wire [W-1:0] word,
    output reg          pdm
);

    reg [W-1:0] acc = 0;

    initial pdm = 1'b0;

    always @(posedge clk)
        {pdm, acc} <= {1'b0, acc} + {1'b0, word};

endmodule
