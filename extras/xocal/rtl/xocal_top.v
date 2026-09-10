//the cc1101's crystal/192 on gdo0 timed against the clock over each pps second
`default_nettype none

module xocal_top #(
    parameter SETTLE   = 54000,
    parameter SEC      = 27000000,
    parameter UART_DIV = 234
) (
    input  wire       clk,
    input  wire       pps,
    input  wire       cc1101_data,
    output wire       cc1101_sck,
    output wire       cc1101_mosi,
    input  wire       cc1101_miso,
    output wire       cc1101_csn,
    output wire       uart_tx,
    output wire [5:0] led
);

    wire cfg_done;
    spi_cfg #(.SETTLE(SETTLE), .IOCFG0_RX(8'h3F)) u_cfg (
        .clk(clk), .sck(cc1101_sck), .mosi(cc1101_mosi), .miso(cc1101_miso),
        .csn(cc1101_csn), .done(cfg_done), .mode(1'b0), .start(1'b0)
    );

    wire        pps_tick, pps_valid;
    wire [31:0] pps_period;
    pps_capture u_pps (
        .clk(clk), .pps(pps), .tick(pps_tick),
        .period(pps_period), .valid(pps_valid)
    );

    reg [31:0] since   = 0;
    reg        has_pps = 1'b0;
    wire fallback = since == SEC + SEC / 2 - 1;
    always @(posedge clk)
        if (pps_tick) begin
            since <= 0; has_pps <= 1'b1;
        end else if (fallback) begin
            since <= SEC / 2; has_pps <= 1'b0;
        end else
            since <= since + 1'b1;

    reg [31:0] p_l = 0;
    always @(posedge clk)
        if (pps_valid)     p_l <= pps_period;
        else if (fallback) p_l <= 0;

    wire [31:0] m, c;
    wire        xo_valid;
    xo_meter u_xo (
        .clk(clk), .gate(pps_tick | fallback), .sig(cc1101_data),
        .m(m), .c(c), .valid(xo_valid)
    );

    function [7:0] hx(input [3:0] v);
        hx = (v < 4'd10) ? 8'h30 + {4'b0, v} : 8'h37 + {4'b0, v};
    endfunction

    reg [95:0] word = 0;
    reg [4:0]  idx  = 0;
    reg        busy = 1'b0;
    wire [4:0] k = idx - ((idx > 5'd18) ? 5'd3 : (idx > 5'd9) ? 5'd2 : 5'd1);
    wire [7:0] tx_byte = (idx == 5'd0)                  ? "X"
                       : (idx == 5'd9 || idx == 5'd18)  ? " "
                       : (idx == 5'd27)                 ? 8'h0A
                       :                                  hx(word[95 - 4 * k -: 4]);
    wire tx_ready;

    always @(posedge clk)
        if (!busy) begin
            if (xo_valid) begin
                word <= {m, c, p_l};
                idx  <= 0;
                busy <= 1'b1;
            end
        end else if (tx_ready) begin
            if (idx == 5'd27) busy <= 1'b0;
            idx <= idx + 1'b1;
        end

    uart_tx #(.DIV(UART_DIV)) u_tx (
        .clk(clk), .data(tx_byte), .valid(busy), .ready(tx_ready), .tx(uart_tx)
    );

    reg beat = 1'b0;
    always @(posedge clk)
        if (xo_valid) beat <= ~beat;

    assign led = ~{beat, 3'b0, has_pps, cfg_done};

endmodule
