//time interval counter, a to b in clk cycles plus a tdc fine on each edge
`default_nettype none

module tic #(
    parameter N   = 1200,
    parameter SEG = 200
) (
    input  wire        clk,
    input  wire        a,
    input  wire        b,
    output reg  [31:0] interval,
    output reg  [11:0] fine_a,
    output reg  [11:0] fine_b,
    output reg         valid
);

    reg [31:0] ctr = 0;
    always @(posedge clk)
        ctr <= ctr + 1'b1;

    reg [2:0] sa = 0, sb = 0;
    always @(posedge clk) begin
        sa <= {sa[1:0], a};
        sb <= {sb[1:0], b};
    end
    wire a_edge = sa[1] & ~sa[2];
    wire b_edge = sb[1] & ~sb[2];

    wire [11:0] fa, fb;
    wire        va, vb;

    tdc #(.N(N), .SEG(SEG)) u_a (.clk(clk), .pps(a), .fine(fa), .valid(va));
    tdc #(.N(N), .SEG(SEG)) u_b (.clk(clk), .pps(b), .fine(fb), .valid(vb));

    localparam IDLE = 2'd0, WAIT_STOP = 2'd1, WAIT_FINES = 2'd2;
    reg [1:0]  st = IDLE;
    reg [31:0] start_c = 0;
    reg [11:0] fa_l = 0, fb_l = 0;
    reg        got_a = 0, got_b = 0;

    always @(posedge clk) begin
        valid <= 1'b0;

        if (va) begin fa_l <= fa; if (st != IDLE)      got_a <= 1'b1; end
        if (vb) begin fb_l <= fb; if (st == WAIT_FINES) got_b <= 1'b1; end

        case (st)
            IDLE:
                if (a_edge) begin
                    start_c <= ctr;
                    got_a   <= 1'b0;
                    got_b   <= 1'b0;
                    if (b_edge) begin        //same edge on both
                        interval <= 0;
                        st       <= WAIT_FINES;
                    end else
                        st <= WAIT_STOP;
                end
            WAIT_STOP:
                if (b_edge) begin
                    interval <= ctr - start_c;
                    got_b    <= 1'b0;
                    st       <= WAIT_FINES;
                end
            WAIT_FINES:
                if (got_a && got_b) begin
                    fine_a <= fa_l;
                    fine_b <= fb_l;
                    valid  <= 1'b1;
                    st     <= IDLE;
                end
            default: st <= IDLE;
        endcase
    end

endmodule
