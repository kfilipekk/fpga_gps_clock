//sends a 36 bit nexus frame as a clean ppm train, REPEATS times
`default_nettype none

module nexus_encode #(
    parameter W = 20,
    parameter [W-1:0] PULSE = 20'd13500,   //500 us
    parameter [W-1:0] ZERO  = 20'd27000,   //gap for a 0
    parameter [W-1:0] ONE   = 20'd54000,   //gap for a 1
    parameter [W-1:0] RESET = 20'd108000,  //between repeats
    parameter         REPEATS = 6
) (
    input  wire        clk,
    input  wire        start,
    input  wire [35:0] frame,
    output reg         bit_out = 1'b0,
    output reg         active  = 1'b0,
    output reg         done    = 1'b0
);

    localparam IDLE = 2'd0, HI = 2'd1, LO = 2'd2, GAP = 2'd3;
    reg [1:0]   st     = IDLE;
    reg [W-1:0] cnt    = 0;
    reg [35:0]  sr     = 0;
    reg [5:0]   bi     = 0;
    reg [7:0]   rep    = 0;
    reg         ending = 1'b0;

    always @(posedge clk) begin
        done <= 1'b0;
        case (st)
            IDLE: begin
                bit_out <= 1'b0; active <= 1'b0;
                if (start) begin
                    sr <= frame; bi <= 0; rep <= REPEATS[7:0]; ending <= 1'b0;
                    cnt <= PULSE; bit_out <= 1'b1; active <= 1'b1; st <= HI;
                end
            end
            HI: begin
                if (cnt <= 1) begin
                    bit_out <= 1'b0;
                    if (ending) begin
                        cnt <= RESET; st <= GAP; ending <= 1'b0;
                    end else begin
                        cnt <= sr[35] ? ONE : ZERO; st <= LO;
                    end
                end else cnt <= cnt - 1'b1;
            end
            LO: begin
                if (cnt <= 1) begin
                    sr <= {sr[34:0], 1'b0};
                    bi <= bi + 6'd1;
                    if (bi == 6'd35) ending <= 1'b1;
                    cnt <= PULSE; bit_out <= 1'b1; st <= HI;
                end else cnt <= cnt - 1'b1;
            end
            GAP: begin
                if (cnt <= 1) begin
                    if (rep <= 1) begin
                        active <= 1'b0; done <= 1'b1; st <= IDLE;
                    end else begin
                        rep <= rep - 1'b1; sr <= frame; bi <= 0;
                        cnt <= PULSE; bit_out <= 1'b1; st <= HI;
                    end
                end else cnt <= cnt - 1'b1;
            end
        endcase
    end

endmodule
