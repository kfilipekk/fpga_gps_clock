//width of every high and low run of the ook envelope, in clk cycles
`default_nettype none

module ook_rx #(
    parameter W    = 24,
    parameter IDLE = 270000
) (
    input  wire         clk,
    input  wire         data,
    output reg          run_level,
    output reg  [W-1:0] run_width,
    output reg          run_valid,
    output reg          sop,
    output reg          eop
);

    reg [2:0] s = 0;
    always @(posedge clk)
        s <= {s[1:0], data};
    wire rise = s[1] & ~s[2];
    wire fall = ~s[1] & s[2];
    wire chg  = rise | fall;

    reg [31:0] cnt  = 0;
    reg        idle = 1'b1;

    initial begin
        run_level = 0;
        run_width = 0;
        run_valid = 0;
        sop       = 0;
        eop       = 0;
    end

    always @(posedge clk) begin
        run_valid <= 1'b0;
        sop       <= 1'b0;
        eop       <= 1'b0;
        if (chg) begin
            run_level <= s[2];
            run_width <= cnt[W-1:0];
            run_valid <= 1'b1;
            cnt       <= 1;
            if (rise) begin
                if (idle) sop <= 1'b1;
                idle <= 1'b0;
            end
        end else begin
            cnt <= cnt + 1'b1;
            if (!s[2] && cnt == IDLE && !idle) begin
                idle <= 1'b1;
                eop  <= 1'b1;
            end
        end
    end

endmodule
