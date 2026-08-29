//recovers the 36 bit nexus frame from the runs
`default_nettype none

module nexus_decode #(
    parameter W = 24,
    parameter [W-1:0] PULSE_MIN = 24'd8100,    //300 us
    parameter [W-1:0] PULSE_MAX = 24'd21600,   //800 us
    parameter [W-1:0] ONE_MIN   = 24'd40500,   //0/1 gap boundary
    parameter [W-1:0] RESET_MIN = 24'd81000    //frame end
) (
    input  wire         clk,
    input  wire         run_level,
    input  wire [W-1:0] run_width,
    input  wire         run_valid,
    input  wire         sop,
    output reg  [35:0]  frame = 0,
    output reg          frame_valid = 1'b0
);

    reg [35:0] sr     = 0;
    reg [5:0]  n      = 0;
    reg        pulsed = 1'b0;

    always @(posedge clk) begin
        frame_valid <= 1'b0;
        if (sop) begin
            n <= 0; pulsed <= 1'b0;
        end else if (run_valid) begin
            if (run_level) begin
                pulsed <= (run_width >= PULSE_MIN) && (run_width <= PULSE_MAX);
            end else if (pulsed) begin
                pulsed <= 1'b0;
                if (run_width >= RESET_MIN) begin
                    if (n == 6'd36 && sr[11:8] == 4'hF) begin
                        frame <= sr; frame_valid <= 1'b1;
                    end
                    n <= 0;
                end else if (n != 6'd36) begin
                    sr <= {sr[34:0], run_width >= ONE_MIN};
                    n  <= n + 6'd1;
                end
            end
        end
    end

endmodule
