//one copy of a triplicated register
`default_nettype none

module tmr_reg #(
    parameter W = 8,
    parameter [W-1:0] INIT = 0
) (
    input  wire         clk,
    input  wire [W-1:0] d,
    output wire [W-1:0] q
);

`ifdef SYNTHESIS
    genvar i;
    generate
        for (i = 0; i < W; i = i + 1) begin : b
            (* keep *) DFF #(.INIT(INIT[i])) u (.CLK(clk), .D(d[i]), .Q(q[i]));
        end
    endgenerate
`else
    reg [W-1:0] r = INIT;
    always @(posedge clk)
        r <= d;
    assign q = r;
`endif

endmodule
