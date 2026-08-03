//free running inverter ring, divided down
`default_nettype none

module ring_osc #(
    //verilator lint_off UNUSEDPARAM
    parameter STAGES = 15,  //odd
    //verilator lint_on UNUSEDPARAM
    parameter DIV    = 13
) (
    input  wire clk,        //sim only
    output wire out
);

`ifdef SYNTHESIS
    (* keep *) wire [STAGES-1:0] ring;

    genvar i;
    generate
        for (i = 0; i < STAGES; i = i + 1) begin : g
            (* keep *)
            LUT1 #(.INIT(2'b01)) u_inv (
                .I0(i == 0 ? ring[STAGES-1] : ring[i-1]),
                .F (ring[i])
            );
        end
    endgenerate

    reg [DIV-1:0] div = 0;
    always @(posedge ring[STAGES-1])
        div <= div + 1'b1;
`else
    reg [DIV-1:0] div = 0;
    always @(posedge clk)
        div <= div + 1'b1;
`endif

    assign out = div[DIV-1];

endmodule
