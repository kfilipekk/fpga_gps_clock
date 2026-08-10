//a second tdc left on the ring and decimated
`default_nettype none

module cal_mon #(
    parameter N        = 1200,
    parameter SEG      = 200,
    parameter DIV      = 13,
    parameter DECIMATE = 64  //power of two
) (
    input  wire        clk,
    output reg  [11:0] fine,
    output reg         valid
);

    wire ring;

    ring_osc #(.DIV(DIV)) u_ring (
        .clk(clk),
        .out(ring)
    );

    wire [11:0] f;
    wire        v;

    tdc #(.N(N), .SEG(SEG)) u_tdc (
        .clk  (clk),
        .pps  (ring),
        .fine (f),
        .valid(v)
    );

    reg [$clog2(DECIMATE)-1:0] cnt = 0;

    initial begin
        fine  = 0;
        valid = 1'b0;
    end

    always @(posedge clk) begin
        valid <= 1'b0;
        if (v) begin
            cnt <= cnt + 1'b1;
            if (&cnt) begin
                fine  <= f;
                valid <= 1'b1;
            end
        end
    end

endmodule
