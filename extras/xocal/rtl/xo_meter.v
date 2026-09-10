//reciprocal counter, m whole periods of sig took c clocks
`default_nettype none

module xo_meter (
    input  wire        clk,
    input  wire        gate,    //one clock strobe
    input  wire        sig,
    output reg  [31:0] m,
    output reg  [31:0] c,
    output reg         valid
);

    reg [2:0] ss = 0;
    always @(posedge clk)
        ss <= {ss[1:0], sig};
    wire sig_edge = ss[1] & ~ss[2];

    reg [31:0] cc   = 0;
    reg [31:0] c0   = 0;
    reg [31:0] n    = 0;
    reg        want = 1'b0;  //gate seen, close on the next edge
    reg        run  = 1'b0;

    initial begin
        m     = 0;
        c     = 0;
        valid = 1'b0;
    end

    always @(posedge clk) begin
        cc    <= cc + 1'b1;
        valid <= 1'b0;
        if (sig_edge) begin
            n <= n + 1'b1;
            if (want || gate) begin
                if (run) begin
                    m     <= n + 1'b1;
                    c     <= cc - c0;
                    valid <= 1'b1;
                end
                c0   <= cc;
                n    <= 0;
                run  <= 1'b1;
                want <= 1'b0;
            end
        end else if (gate)
            want <= 1'b1;
    end

endmodule
