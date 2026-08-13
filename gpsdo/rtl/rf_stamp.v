//stamps each evt edge as {second, clk cycles into it, tdc fine}
`default_nettype none

module rf_stamp #(
    parameter N   = 1200,
    parameter SEG = 200
) (
    input  wire        clk,
    input  wire        pps,
    input  wire        evt,
    output reg  [31:0] sec,
    output reg  [31:0] sub,
    output reg  [11:0] fine,
    output reg         valid
);

    reg [2:0] sp = 0, se = 0;
    always @(posedge clk) begin
        sp <= {sp[1:0], pps};
        se <= {se[1:0], evt};
    end
    wire pps_edge = sp[1] & ~sp[2];
    wire evt_edge = se[1] & ~se[2];

    reg [31:0] secs  = 0;
    reg [31:0] phase = 0;
    //1 not 0, so sub is the exact count since the edge
    always @(posedge clk)
        if (pps_edge) begin
            secs  <= secs + 1'b1;
            phase <= 1;
        end else begin
            phase <= phase + 1'b1;
        end

    wire [11:0] fe;
    wire        ve;
    tdc #(.N(N), .SEG(SEG)) u_tdc (.clk(clk), .pps(evt), .fine(fe), .valid(ve));

    reg [31:0] sec_l = 0, sub_l = 0;
    reg        pend  = 0;

    initial begin
        sec = 0; sub = 0; fine = 0; valid = 0;
    end

    always @(posedge clk) begin
        valid <= 1'b0;
        if (evt_edge && !pend) begin
            sec_l <= secs;
            sub_l <= phase;
            pend  <= 1'b1;
        end
        if (pend && ve) begin
            sec   <= sec_l;
            sub   <= sub_l;
            fine  <= fe;
            valid <= 1'b1;
            pend  <= 1'b0;
        end
    end

endmodule
