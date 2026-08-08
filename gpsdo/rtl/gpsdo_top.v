//one line per pps, PPPPPPPP FFF: clk cycles
`default_nettype none

module gpsdo_top #(
    parameter UART_DIV = 234,
    parameter TDC_N    = 1200,
    parameter BTN_HOLD = 270000,
    parameter LOSS     = 40000000  //no pps for ~1.5 s trips holdover
) (
    input  wire       clk,
    input  wire       pps,
    input  wire       btn_s1,
    output wire       uart_tx,
    output wire       efc,
    output wire [5:0] led
);

    wire cal;

    btn_toggle #(.HOLD(BTN_HOLD)) u_mode (
        .clk  (clk),
        .btn  (btn_s1),
        .state(cal)
    );

    wire ring;

    ring_osc u_ring (
        .clk(clk),
        .out(ring)
    );

    wire trig = cal ? ring : pps;

    wire        tick;
    wire [31:0] period;
    wire        valid;

    pps_capture u_capture (
        .clk    (clk),
        .pps    (trig),
        .tick   (tick),
        .period (period),
        .valid  (valid)
    );

    wire [11:0] fine;
    wire        tdc_valid;

    tdc #(.N(TDC_N)) u_tdc (
        .clk  (clk),
        .pps  (trig),  //raw, the chain does the sampling
        .fine (fine),
        .valid(tdc_valid)
    );

    //the period lands long before the fine, so it is always ready
    reg [31:0] p_lat  = 0;
    reg        have_p = 1'b0;

    always @(posedge clk)
        if (valid) begin
            p_lat  <= period;
            have_p <= 1'b1;
        end

    reg  [31:0] p_snap   = 0;
    reg  [11:0] f_snap   = 0;
    reg  [3:0]  idx      = 0;
    reg         sending  = 1'b0;
    reg         tx_valid = 1'b0;
    wire        tx_ready;

    wire [3:0] nib = (idx < 8)   ? p_snap[(4'd7 - idx) * 4 +: 4] :
                     (idx == 9)  ? f_snap[11:8] :
                     (idx == 10) ? f_snap[7:4]  :
                                   f_snap[3:0];

    wire [7:0] tx_byte = (idx == 8)  ? 8'h20 :
                         (idx == 12) ? 8'h0A :
                         (nib < 10)  ? 8'h30 + {4'b0, nib} :
                                       8'h37 + {4'b0, nib};

    always @(posedge clk) begin
        if (!sending && tdc_valid && have_p) begin
            p_snap   <= p_lat;
            f_snap   <= fine;
            idx      <= 4'd0;
            sending  <= 1'b1;
            tx_valid <= 1'b1;
        end else if (sending && tx_ready && tx_valid) begin
            idx <= idx + 4'd1;
            if (idx == 4'd12) begin
                sending  <= 1'b0;
                tx_valid <= 1'b0;
            end
        end
    end

    uart_tx #(.DIV(UART_DIV)) u_uart (
        .clk   (clk),
        .data  (tx_byte),
        .valid (tx_valid),
        .ready (tx_ready),
        .tx    (uart_tx)
    );

    reg [$clog2(LOSS)-1:0] since = 0;
    wire hold = since == LOSS - 1;
    always @(posedge clk)
        if (tick)          since <= 0;
        else if (!hold)    since <= since + 1'b1;

    //only real pps edges feed the loop, not the ring
    localparam [31:0] NOMINAL = 32'd27000000;
    wire signed [31:0] freq_err = $signed(period) - $signed(NOMINAL);
    wire loop_valid = valid && !cal;

    wire [15:0] dac_word;
    wire        locked;

    disc_loop u_loop (
        .clk   (clk),
        .valid (loop_valid),
        .err   (freq_err),
        .hold  (hold),
        .dac   (dac_word),
        .locked(locked)
    );

    sd_dac u_dac (
        .clk (clk),
        .word(dac_word),
        .pdm (efc)
    );

    reg pps_led = 1'b0;
    always @(posedge clk)
        if (tick) pps_led <= ~pps_led;

    reg [23:0] beat     = 0;
    reg        beat_led = 1'b0;
    always @(posedge clk) begin
        beat <= beat + 1'b1;
        if (beat == 0) beat_led <= ~beat_led;
    end

    assign led = ~{beat_led, 1'b0, hold, locked, cal, pps_led};

endmodule
