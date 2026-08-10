//wave union, CHAINS chains on the same edge with their codes summed
`default_nettype none

module tdc_wu #(
    parameter N      = 1200,
    parameter SEG    = 200,
    parameter CHAINS = 4
) (
    input  wire                       clk,
    input  wire                       pps,
    output reg  [11+$clog2(CHAINS):0] fine,
    output wire                       valid
);

    wire [CHAINS-1:0]    v;
    wire [12*CHAINS-1:0] fbus;

    genvar i;
    generate
        for (i = 0; i < CHAINS; i = i + 1) begin : ch
            tdc #(.N(N), .SEG(SEG)) u_tdc (
                .clk  (clk),
                .pps  (pps),
                .fine (fbus[i*12 +: 12]),
                .valid(v[i])
            );
        end
    endgenerate

    //same N and trigger, so every core finishes on the same clock
    integer k;
    always @* begin
        fine = 0;
        for (k = 0; k < CHAINS; k = k + 1)
            fine = fine + {{$clog2(CHAINS){1'b0}}, fbus[k*12 +: 12]};
    end

    assign valid = &v;

endmodule
