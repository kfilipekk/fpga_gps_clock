//one line per pps, PPPPPPPP FFF OOOOOOOO DDDD: clk cycles, tdc taps, ocxo
//cycles and the efc word. ring calibration lines stop after FFF
`default_nettype none

module gpsdo_top #(
    parameter UART_DIV = 234,
    parameter TDC_N    = 1200,
    parameter BTN_HOLD = 270000,
    parameter LOSS     = 40000000, //no pps for ~1.5 s trips holdover
    parameter OCXO_HZ  = 10000000,
    parameter WINDOW   = 50,       //counts off nominal the loop will act on
    parameter ERR_SHIFT = 8,       //one efc lsb is ~4e-4 counts, so scale up
    parameter KP       = 16,
    parameter KI       = 3
) (
    input  wire       clk,
    input  wire       pps,
    input  wire       ocxo,
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

    reg [$clog2(LOSS)-1:0] since = 0;
    wire hold = since == LOSS - 1;
    always @(posedge clk)
        if (tick)          since <= 0;
        else if (!hold)    since <= since + 1'b1;

    //the ocxo counted over each gps second. it is sampled on clk, not used
    //as a clock: through the divider its edges are too slow to clock flops
    //cleanly and double counted on silicon. at 10 mhz every high and low is
    //wider than one 37 ns clk, so no edge is missed. the raw pps gates it,
    //so ring calibration does not disturb it
    reg [2:0] o_s = 3'b000;
    reg [2:0] g_s = 3'b000;
    always @(posedge clk) begin
        o_s <= {o_s[1:0], ocxo};
        g_s <= {g_s[1:0], pps};
    end
    wire o_edge = o_s[1] & ~o_s[2];
    wire g_tick = g_s[1] & ~g_s[2];

    //an edge on a tick starts the next count, so runs of counts telescope
    reg [31:0] o_cnt   = 0;
    reg [31:0] o_lat   = 0;
    reg        o_armed = 1'b0;
    reg        o_new   = 1'b0;
    always @(posedge clk) begin
        o_new <= 1'b0;
        if (g_tick) begin
            o_cnt   <= {31'd0, o_edge};
            o_armed <= 1'b1;
            if (o_armed) begin
                o_lat <= o_cnt;
                o_new <= 1'b1;
            end
        end else
            o_cnt <= o_cnt + {31'd0, o_edge};
    end

    //positive when the ocxo runs slow, and efc has a positive slope. the
    //sum of these is its phase against gps in cycles, so the integral
    //term holds phase and the loop pulls frequency error to zero
    wire signed [31:0] o_err  = $signed(OCXO_HZ) - $signed(o_lat);
    wire               o_near = o_err < $signed(WINDOW) && o_err > -$signed(WINDOW);
    wire signed [31:0] loop_err = o_err <<< ERR_SHIFT;

    //a missing or warming ocxo stays out of the integrator
    wire loop_valid = o_new && o_near && !cal;

    wire [15:0] dac_word;
    wire        locked;

    disc_loop #(
        .KP      (KP),
        .KI      (KI),
        .LOCK_ERR(2 << ERR_SHIFT),
        .LOCK_N  (32)
    ) u_loop (
        .clk   (clk),
        .valid (loop_valid),
        .err   (loop_err),
        .hold  (hold),
        .dac   (dac_word),
        .locked(locked)
    );

    sd_dac u_dac (
        .clk (clk),
        .word(dac_word),
        .pdm (efc)
    );

    reg  [31:0] p_snap   = 0;
    reg  [11:0] f_snap   = 0;
    reg  [31:0] o_snap   = 0;
    reg  [15:0] d_snap   = 0;
    reg         short    = 1'b0;  //ring lines stay short, for sample rate
    reg  [4:0]  idx      = 0;
    reg         sending  = 1'b0;
    reg         tx_valid = 1'b0;
    wire        tx_ready;

    wire [3:0] nib = (idx < 8)               ? p_snap[(5'd7 - idx) * 4 +: 4] :
                     (idx == 9)              ? f_snap[11:8] :
                     (idx == 10)             ? f_snap[7:4]  :
                     (idx == 11)             ? f_snap[3:0]  :
                     (idx > 12 && idx < 21)  ? o_snap[(5'd20 - idx) * 4 +: 4] :
                     (idx > 21 && idx < 26)  ? d_snap[(5'd25 - idx) * 4 +: 4] :
                                               4'd0;

    wire last = short ? idx == 5'd12 : idx == 5'd26;

    wire [7:0] tx_byte = last                                    ? 8'h0A :
                         (idx == 8 || idx == 12 || idx == 21)    ? 8'h20 :
                         (nib < 10) ? 8'h30 + {4'b0, nib} :
                                      8'h37 + {4'b0, nib};

    always @(posedge clk) begin
        if (!sending && tdc_valid && have_p) begin
            p_snap   <= p_lat;
            f_snap   <= fine;
            o_snap   <= o_lat;
            d_snap   <= dac_word;
            short    <= cal;
            idx      <= 5'd0;
            sending  <= 1'b1;
            tx_valid <= 1'b1;
        end else if (sending && tx_ready && tx_valid) begin
            idx <= idx + 5'd1;
            if (last) begin
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
