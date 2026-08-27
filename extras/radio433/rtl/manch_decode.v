//manchester (biphase-l) off edge timing
`default_nettype none

module manch_decode #(
    parameter PW = 16,
    parameter [PW-1:0] HALF = 13500     //half a bit, clk cycles
) (
    input  wire clk,
    input  wire sig,
    output reg  db = 1'b0,
    output reg  db_valid = 1'b0
);

    reg [2:0] s = 0;
    always @(posedge clk) s <= {s[1:0], sig};
    wire edg = s[1] ^ s[2];

    localparam [PW-1:0] FULLTH = HALF + (HALF >> 1);
    localparam [PW-1:0] IDLEG  = HALF << 2;           //frame end

    reg [PW-1:0] cnt = 0;
    reg          last_mid = 1'b0;
    reg          armed    = 1'b0;

    always @(posedge clk) begin
        db_valid <= 1'b0;
        if (edg) begin
            if (!armed) begin
                armed <= 1'b1; last_mid <= 1'b0;
            end else if (cnt >= FULLTH) begin
                db <= s[1]; db_valid <= 1'b1; last_mid <= 1'b1;
            end else if (last_mid) begin
                last_mid <= 1'b0;
            end else begin
                db <= s[1]; db_valid <= 1'b1; last_mid <= 1'b1;
            end
            cnt <= 0;
        end else begin
            if (cnt == IDLEG) armed <= 1'b0;
            cnt <= cnt + 1'b1;
        end
    end

endmodule
