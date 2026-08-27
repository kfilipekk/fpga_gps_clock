//matches the sync word then collects PAYLOAD_LEN bits
`default_nettype none

module sync_frame #(
    parameter SYNC_LEN     = 16,
    parameter [15:0] SYNC  = 16'hD391,
    parameter PAYLOAD_LEN  = 32,
    parameter CRC_CHECK    = 0,
    parameter [7:0] CRC_POLY = 8'h07,
    parameter [7:0] CRC_INIT = 8'h00
) (
    input  wire                      clk,
    input  wire                      db,
    input  wire                      db_valid,
    input  wire                      sop,
    input  wire                      eop,
    output reg  [PAYLOAD_LEN-1:0]    payload = 0,
    output reg                       payload_valid = 1'b0
);

    //one short, the incoming bit joins the match directly
    reg [SYNC_LEN-2:0] sh = 0;
    reg [7:0]          cnt = 0;
    reg                collecting = 0;

    reg  [7:0] crc = CRC_INIT;
    wire [7:0] crc_nx = {crc[6:0], 1'b0} ^ ((crc[7] ^ db) ? CRC_POLY : 8'h00);
    wire       is_crc = CRC_CHECK && (cnt == PAYLOAD_LEN - 1) &&
                        (crc == {payload[6:0], db});

    always @(posedge clk) begin
        payload_valid <= 1'b0;
        if (sop || eop) begin
            sh <= 0; cnt <= 0; collecting <= 1'b0;
        end else if (db_valid) begin
            sh <= {sh[SYNC_LEN-3:0], db};
            if (collecting) begin
                payload <= {payload[PAYLOAD_LEN-2:0], db};
                if (cnt < PAYLOAD_LEN - 8) crc <= crc_nx;
                if (cnt == PAYLOAD_LEN - 1)
                    payload_valid <= CRC_CHECK ? is_crc : 1'b1;
                cnt <= cnt + 1'b1;
            end else if ({sh[SYNC_LEN-2:0], db} == SYNC[SYNC_LEN-1:0]) begin
                collecting <= 1'b1;
                cnt <= 0; crc <= CRC_INIT;
            end
        end
    end

endmodule
