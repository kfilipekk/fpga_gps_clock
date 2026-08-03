//pi loop from frequency error to a dac word for the vctcxo
`default_nettype none

module disc_loop #(
    parameter EW = 32,
    parameter DW = 16,
    parameter IW = 48,
    parameter KP = 8,         //gains are right shifts
    parameter KI = 16,
    parameter LOCK_ERR = 8,
    parameter LOCK_N = 8,
    parameter TMR = 0
) (
    input  wire                 clk,
    input  wire                 valid,
    input  wire signed [EW-1:0] err,
    input  wire                 hold,
    output wire [DW-1:0]        dac,
    output reg                  locked
);

    localparam signed [IW-1:0] MID  = 1 <<< (DW - 1);
    localparam signed [IW-1:0] FULL = (1 <<< DW) - 1;

    reg [$clog2(LOCK_N+1)-1:0] good = 0;
    initial locked = 1'b0;

    wire upd = valid && !hold;
    wire signed [IW-1:0] integ;
    wire signed [IW-1:0] integ_n;
    wire [DW-1:0] dac_n;

    generate
        if (TMR) begin : t
            wire [IW-1:0] i0, i1, i2;
            wire [DW-1:0] d0, d1, d2;
            wire [IW-1:0] in = upd ? integ_n : integ;
            wire [DW-1:0] dn = upd ? dac_n : dac;
            tmr_reg #(.W(IW)) u_i0 (.clk(clk), .d(in), .q(i0));
            tmr_reg #(.W(IW)) u_i1 (.clk(clk), .d(in), .q(i1));
            tmr_reg #(.W(IW)) u_i2 (.clk(clk), .d(in), .q(i2));
            tmr_reg #(.W(DW), .INIT(1 << (DW - 1))) u_d0 (.clk(clk), .d(dn), .q(d0));
            tmr_reg #(.W(DW), .INIT(1 << (DW - 1))) u_d1 (.clk(clk), .d(dn), .q(d1));
            tmr_reg #(.W(DW), .INIT(1 << (DW - 1))) u_d2 (.clk(clk), .d(dn), .q(d2));
            assign integ = (i0 & i1) | (i1 & i2) | (i0 & i2);
            assign dac   = (d0 & d1) | (d1 & d2) | (d0 & d2);
        end else begin : s
            reg signed [IW-1:0] i0 = 0;
            reg [DW-1:0] d0 = 1 << (DW - 1);
            always @(posedge clk)
                if (upd) begin
                    i0 <= integ_n;
                    d0 <= dac_n;
                end
            assign integ = i0;
            assign dac   = d0;
        end
    endgenerate

    wire signed [IW-1:0] err_x = {{(IW-EW){err[EW-1]}}, err};
    assign integ_n = integ + err_x;
    wire signed [IW-1:0] ctrl = MID + (err_x >>> KP) + (integ_n >>> KI);
    assign dac_n = (ctrl < 0)    ? {DW{1'b0}} :
                   (ctrl > FULL) ? {DW{1'b1}} : ctrl[DW-1:0];

    wire in_win = (err < $signed(LOCK_ERR)) && (err > -$signed(LOCK_ERR));

    always @(posedge clk)
        if (upd) begin
            if (!in_win)
                good <= 0;
            else if (good != LOCK_N)
                good <= good + 1'b1;
            locked <= in_win && (good >= LOCK_N - 1);
        end

endmodule
