//high runs longer than the threshold are 1s
`default_nettype none

module pwm_slice #(
    parameter W     = 24,
    parameter [W-1:0] THRESH = 24'd20250,
    parameter ADAPT = 0
) (
    input  wire         clk,
    input  wire         sop,
    input  wire         run_level,
    input  wire [W-1:0] run_width,
    input  wire         run_valid,
    output reg          db = 1'b0,
    output reg          db_valid = 1'b0
);

    reg [W-1:0] wmin = {W{1'b1}};
    reg [W-1:0] wmax = 0;
    reg [W-1:0] th   = THRESH;
    wire [W-1:0] nmin = (run_width < wmin) ? run_width : wmin;
    wire [W-1:0] nmax = (run_width > wmax) ? run_width : wmax;

    always @(posedge clk) begin
        db_valid <= 1'b0;
        if (sop) begin
            wmin <= {W{1'b1}}; wmax <= 0; th <= THRESH;
        end else if (run_valid && run_level) begin
            db       <= run_width > (ADAPT ? th : THRESH);
            db_valid <= 1'b1;
            if (ADAPT != 0) begin
                wmin <= nmin; wmax <= nmax; th <= (nmin + nmax) >> 1;
            end
        end
    end

endmodule
