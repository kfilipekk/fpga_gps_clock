//carry chain tdc, where in the clock cycle the edge landed, in taps
`default_nettype none

module tdc #(
    parameter N   = 1200,
    parameter SEG = 200
) (
    input  wire        clk,
    input  wire        pps,
    output wire [11:0] fine,
    output wire        valid
);

    wire [N-1:0] taps;

    tdc_chain #(.N(N), .SEG(SEG)) u_chain (
        .trig(pps),
        .taps(taps)
    );

    tdc_core #(.N(N)) u_core (
        .clk  (clk),
        .trig (pps),
        .taps (taps),
        .fine (fine),
        .valid(valid)
    );

endmodule
