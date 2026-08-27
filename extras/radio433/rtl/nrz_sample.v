//nrz bit recovery for a cc1101 in packet mode
`default_nettype none

module nrz_sample #(
    parameter PW = 15,
    parameter [PW-1:0] BIT_CYCLES = 27000   //clk / baud
) (
    input  wire clk,
    input  wire sig,
    output reg  db = 1'b0,
    output reg  db_valid = 1'b0
);

    reg [2:0] s = 0;
    always @(posedge clk) s <= {s[1:0], sig};
    wire chg = s[1] ^ s[2];

    localparam [PW-1:0] MID = BIT_CYCLES >> 1;
    reg [PW-1:0] phase = 0;

    always @(posedge clk) begin
        db_valid <= 1'b0;
        if (phase == MID) begin
            db       <= s[2];
            db_valid <= 1'b1;
        end
        if (chg)                        phase <= 0;
        else if (phase == BIT_CYCLES-1) phase <= 0;
        else                            phase <= phase + 1'b1;
    end

endmodule
