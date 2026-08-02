//alu carry chain delay line in SEG long segments joined by lut hops
`default_nettype none

module tdc_chain #(
    parameter N = 1200,
    //verilator lint_off UNUSEDPARAM
    parameter SEG = 200
    //verilator lint_on UNUSEDPARAM
) (
    input  wire         trig,
    output wire [N-1:0] taps
);

`ifdef VERILATOR
    assign taps = {N{trig}};
`elsif SYNTHESIS
    localparam NSEG = (N + SEG - 1) / SEG;

    wire [N-1:0]    sum_n;
    wire [NSEG-1:0] seg_in;
    assign seg_in[0] = trig;

    genvar s, i;
    generate
        for (s = 0; s < NSEG; s = s + 1) begin : seg
            localparam LO = s * SEG;
            localparam HI = (LO + SEG <= N) ? LO + SEG : N;
            wire [HI-LO:0] c;
            assign c[0] = seg_in[s];
            for (i = 0; i < HI - LO; i = i + 1) begin : g
                (* keep *)
                ALU #(.ALU_MODE(0)) u_alu (
                    .I0  (1'b1),
                    .I1  (1'b0),
                    .I3  (1'b0),
                    .CIN (c[i]),
                    .COUT(c[i + 1]),
                    .SUM (sum_n[LO + i])
                );
            end
            if (s < NSEG - 1) begin : h
                (* keep *)
                LUT1 #(.INIT(2'b10)) u_hop (
                    .I0(c[HI - LO]),
                    .F (seg_in[s + 1])
                );
            end
        end
    endgenerate

    //sum is ~cin in this mode
    assign taps = ~sum_n;
`else
    assign taps = {N{trig}};
`endif

endmodule
