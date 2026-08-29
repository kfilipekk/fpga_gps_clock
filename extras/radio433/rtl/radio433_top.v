//433 mhz ook receiver
`default_nettype none

module radio433_top #(
    parameter UART_DIV = 234,
    parameter IDLE     = 270000,
    parameter TDC_N    = 1200,
    parameter GLITCH_K     = 6750,
    parameter PWM_THRESH   = 20250,
    parameter NRZ          = 0,       //1 for a cc1101 in packet mode
    parameter MANCH        = 0,
    parameter PWM_ADAPT    = 0,
    parameter BIT_CYCLES   = 27000,   //nrz, clk / baud
    parameter MANCH_HALF   = 13500,
    parameter [15:0] SYNC  = 16'hD391,
    parameter SYNC_LEN     = 16,
    parameter PAYLOAD_LEN  = 32,
    parameter CRC_CHECK    = 0,
    parameter [7:0] CRC_POLY = 8'h07,
    parameter [7:0] CRC_INIT = 8'h00,
    parameter [23:0] CC_FREQ = 24'h10B071, //see ../xocal
    parameter NX_PULSE_MIN = 8100,
    parameter NX_PULSE_MAX = 21600,
    parameter NX_ONE_MIN   = 40500,
    parameter NX_RESET_MIN = 81000,
    parameter NX_PULSE     = 13500,
    parameter NX_ZERO      = 27000,
    parameter NX_ONE       = 54000,
    parameter NX_RESET     = 108000,
    parameter NX_REPEATS   = 6
) (
    input  wire       clk,
    input  wire       pps,
    inout  wire       cc1101_data,
    output wire       cc1101_sck,
    output wire       cc1101_mosi,
    input  wire       cc1101_miso,
    output wire       cc1101_csn,
    output wire       uart_tx,
    input  wire       uart_rx,
    output wire [5:0] led
);

    //gdo0 is the envelope in rx and the fpga's drive in tx
    reg  tx_oe  = 1'b0;
    reg  tx_bit = 1'b0;
    assign cc1101_data = tx_oe ? tx_bit : 1'bz;
    wire rx_env = cc1101_data;

    wire cfg_done;
    reg  cfg_mode = 1'b0, cfg_start = 1'b0;
    spi_cfg #(.FREQ(CC_FREQ)) u_cfg (
        .clk(clk), .sck(cc1101_sck), .mosi(cc1101_mosi),
        .miso(cc1101_miso), .csn(cc1101_csn), .done(cfg_done),
        .mode(cfg_mode), .start(cfg_start)
    );

    //receive is held idle while transmitting so our own tx isnt captured
    reg  txmode = 1'b0;
    wire filt_out;
    glitch_filt #(.K(GLITCH_K)) u_filt (
        .clk(clk), .din(rx_env), .out(filt_out)
    );
    wire clean = txmode ? 1'b0 : filt_out;

    wire [7:0] rx_data;
    wire       rx_valid;
    uart_rx #(.DIV(UART_DIV)) u_rx (
        .clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid)
    );

    reg replay_cmd = 1'b0;
    always @(posedge clk)
        if (rx_valid && rx_data == "T") replay_cmd <= 1'b1;
        else replay_cmd <= 1'b0;

    reg transcode_cmd = 1'b0;
    always @(posedge clk)
        if (rx_valid && rx_data == "C") transcode_cmd <= 1'b1;
        else transcode_cmd <= 1'b0;

    wire        rl;
    wire [23:0] rw;
    wire        rv, sop, eop;

    ook_rx #(.W(24), .IDLE(IDLE)) u_ook (
        .clk(clk), .data(clean),
        .run_level(rl), .run_width(rw), .run_valid(rv),
        .sop(sop), .eop(eop)
    );

    wire db, bv;
    generate
        if (MANCH) begin : g_manch
            manch_decode #(.HALF(MANCH_HALF)) u_dec (
                .clk(clk), .sig(clean), .db(db), .db_valid(bv)
            );
        end else if (NRZ) begin : g_nrz
            nrz_sample #(.BIT_CYCLES(BIT_CYCLES)) u_dec (
                .clk(clk), .sig(clean), .db(db), .db_valid(bv)
            );
        end else begin : g_pwm
            pwm_slice #(.THRESH(PWM_THRESH), .ADAPT(PWM_ADAPT)) u_dec (
                .clk(clk), .sop(sop), .run_level(rl), .run_width(rw),
                .run_valid(rv), .db(db), .db_valid(bv)
            );
        end
    endgenerate

    wire [PAYLOAD_LEN-1:0] payload;
    wire payload_valid;
    sync_frame #(.SYNC_LEN(SYNC_LEN), .SYNC(SYNC), .PAYLOAD_LEN(PAYLOAD_LEN),
                 .CRC_CHECK(CRC_CHECK), .CRC_POLY(CRC_POLY), .CRC_INIT(CRC_INIT)) u_frame (
        .clk(clk), .db(db), .db_valid(bv), .sop(sop), .eop(eop),
        .payload(payload), .payload_valid(payload_valid)
    );

    reg [PAYLOAD_LEN-1:0] dec_payload = 0;
    reg                   dec_matched = 0;
    always @(posedge clk) begin
        if (sop) dec_matched <= 1'b0;
        if (payload_valid) begin
            dec_payload <= payload;
            dec_matched <= 1'b1;
        end
    end

    reg [PAYLOAD_LEN-1:0] dd_payload = 0;
    reg                   dd_matched = 0;
    always @(posedge clk) begin
        if (eop) begin
            dd_payload <= dec_payload;
            dd_matched <= dec_matched;
        end
    end

    //the frame is sticky, so 'C' still works after a noise packet
    wire [35:0] nx_frame;
    wire        nx_valid;
    nexus_decode #(.PULSE_MIN(NX_PULSE_MIN), .PULSE_MAX(NX_PULSE_MAX),
                   .ONE_MIN(NX_ONE_MIN), .RESET_MIN(NX_RESET_MIN)) u_nxd (
        .clk(clk), .run_level(rl), .run_width(rw), .run_valid(rv), .sop(sop),
        .frame(nx_frame), .frame_valid(nx_valid)
    );
    reg [35:0] tx_nexus = 0;
    reg        tx_nexus_ok = 1'b0;
    always @(posedge clk)
        if (nx_valid) begin tx_nexus <= nx_frame; tx_nexus_ok <= 1'b1; end

    reg  enc_start = 1'b0;
    wire enc_bit, enc_active, enc_done;
    nexus_encode #(.PULSE(NX_PULSE), .ZERO(NX_ZERO), .ONE(NX_ONE),
                   .RESET(NX_RESET), .REPEATS(NX_REPEATS)) u_nxe (
        .clk(clk), .start(enc_start), .frame(tx_nexus),
        .bit_out(enc_bit), .active(enc_active), .done(enc_done)
    );

    wire [31:0] s_sec, s_sub;
    wire [11:0] s_fine;
    wire        s_valid;

    rf_stamp #(.N(TDC_N)) u_stamp (
        .clk(clk), .pps(pps), .evt(clean),
        .sec(s_sec), .sub(s_sub), .fine(s_fine), .valid(s_valid)
    );

    //the gpsdo's pps line, tap field 000: a second tdc choked place and route
    wire        pps_tick;
    wire [31:0] pps_period;
    wire        pps_period_valid;
    pps_capture u_pps (
        .clk(clk), .pps(pps), .tick(pps_tick),
        .period(pps_period), .valid(pps_period_valid)
    );

    reg [31:0] pps_period_l = 0;
    reg [11:0] pps_fine_l = 0;
    reg        pps_pend = 1'b0;

    reg [31:0] ts_sec = 0, ts_sub = 0;
    reg [11:0] ts_fine = 0;
    reg        cap = 0;
    always @(posedge clk) begin
        if (sop) cap <= 1'b1;
        if (cap && s_valid) begin
            ts_sec <= s_sec; ts_sub <= s_sub; ts_fine <= s_fine;
            cap <= 1'b0;
        end
    end

    localparam CAP = 3'd0, D_TS = 3'd1, D_DEC = 3'd2, D_RUN = 3'd3, D_PPS = 3'd4;
    localparam DEC_HEX = PAYLOAD_LEN / 4;
    reg  [2:0]  st = CAP;
    reg  [24:0] pktbuf [0:255];
    reg  [7:0]  wptr = 0, rptr = 0, len = 0;
    reg         capturing = 1'b0;

    always @(posedge clk)
        if (sop) capturing <= 1'b1;
        else if (eop) capturing <= 1'b0;
    reg  [24:0] rdata = 0;
    reg  [31:0] dts_sec = 0, dts_sub = 0;
    reg  [11:0] dts_fine = 0;
    reg         truncd = 0;

    always @(posedge clk) rdata <= pktbuf[rptr];

    //pps lines only go out between packets
    wire pps_go = (st == CAP) && !sop && !eop && !capturing && pps_pend;

    always @(posedge clk) begin
        if (pps_period_valid) begin
            pps_period_l <= pps_period;
            pps_pend <= 1'b1;
        end else if (pps_go) begin
            pps_pend <= 1'b0;
        end
    end

    //own read pointer so a replay never races the dump
    reg  [7:0]  tx_rptr = 0;
    reg  [24:0] tx_rdata = 0;
    always @(posedge clk) tx_rdata <= pktbuf[tx_rptr];

    reg  [4:0] idx      = 0;
    reg        tx_valid = 0;
    wire       tx_ready;
    //the D line fits a 5 bit index while PAYLOAD_LEN <= 124
    wire [4:0] last = (st == D_TS)  ? 5'd22
                    : (st == D_DEC) ? DEC_HEX[4:0] + 5'd1
                    : (st == D_PPS) ? 5'd12
                    :                 5'd8;

    function [7:0] hx(input [3:0] n);
        hx = (n < 10) ? 8'h30 + {4'b0, n} : 8'h37 + {4'b0, n};
    endfunction

    reg [7:0] tx_byte;
    //clamped so an unreachable idx is still a legal part select
    wire [4:0] dbase = (idx >= 5'd1 && idx <= DEC_HEX[4:0])
                     ? ((DEC_HEX[4:0] - idx) << 2) : 5'd0;
    always @* begin
        case (st)
            D_TS: begin
                case (idx)
                    5'd0:    tx_byte = "@";
                    5'd9:    tx_byte = " ";
                    5'd18:   tx_byte = " ";
                    5'd22:   tx_byte = 8'h0A;
                    default: tx_byte = (idx < 9)  ? hx(dts_sec[(5'd8  - idx) * 4 +: 4])
                                     : (idx < 18) ? hx(dts_sub[(5'd17 - idx) * 4 +: 4])
                                     :              hx(dts_fine[(5'd21 - idx) * 4 +: 4]);
                endcase
            end
            D_DEC: begin
                case (idx)
                    5'd0:    tx_byte = "D";
                    default: tx_byte = (idx == DEC_HEX[4:0] + 5'd1) ? 8'h0A
                                     : hx(dd_payload[dbase +: 4]);
                endcase
            end
            D_PPS: begin
                case (idx)
                    5'd8:    tx_byte = " ";
                    5'd12:   tx_byte = 8'h0A;
                    default: tx_byte = (idx < 8) ? hx(pps_period_l[(5'd7 - idx) * 4 +: 4])
                                     :             hx(pps_fine_l[(5'd11 - idx) * 4 +: 4]);
                endcase
            end
            default: begin
                case (idx)
                    5'd0:    tx_byte = "R";
                    5'd1:    tx_byte = rdata[24] ? "1" : "0";
                    5'd8:    tx_byte = 8'h0A;
                    default: tx_byte = hx(rdata[(5'd7 - idx) * 4 +: 4]);
                endcase
            end
        endcase
    end

    always @(posedge clk) begin
        case (st)
            CAP: begin
                if (sop) begin wptr <= 0; truncd <= 0; end
                else if (rv) begin
                    if (wptr != 8'd255) begin
                        pktbuf[wptr] <= {rl, rw};
                        wptr <= wptr + 8'd1;
                    end else truncd <= 1'b1;
                end
                if (eop) begin
                    len <= wptr; idx <= 0; st <= D_TS;
                    dts_sec <= ts_sec; dts_sub <= ts_sub; dts_fine <= ts_fine;
                end else if (pps_go) begin
                    idx <= 0; st <= D_PPS;
                end
            end
            D_TS, D_DEC, D_RUN, D_PPS: begin
                tx_valid <= 1'b1;
                if (tx_ready && tx_valid) begin
                    if (idx == last) begin
                        tx_valid <= 1'b0; idx <= 0;
                        if (st == D_TS) begin
                            if (len == 0) st <= CAP;
                            else if (dd_matched) st <= D_DEC;
                            else st <= D_RUN;
                        end else if (st == D_DEC) begin
                            st <= D_RUN; rptr <= 0;
                        end else if (st == D_PPS) begin
                            st <= CAP;
                        end else if (rptr == len - 8'd1) begin
                            st <= CAP;
                        end else begin
                            rptr <= rptr + 8'd1;
                        end
                    end else idx <= idx + 5'd1;
                end
            end
            default: st <= CAP;
        endcase
    end

    uart_tx #(.DIV(UART_DIV)) u_uart (
        .clk(clk), .data(tx_byte), .valid(tx_valid),
        .ready(tx_ready), .tx(uart_tx)
    );

    //retransmit: cc1101 to tx, play the runs or the clean frame out gdo0
    localparam RIDLE = 3'd0, RCFG_TX = 3'd1, RTX = 3'd2, RCFG_RX = 3'd3,
               RENC = 3'd4;
    reg [2:0]  st_r      = RIDLE;
    reg [23:0] tx_cnt    = 0;
    reg        tx_pend   = 1'b0;
    reg        cfg_started = 1'b0;
    reg        cfg_low   = 1'b0;
    reg        transcode = 1'b0;

    always @(posedge clk) begin
        case (st_r)
            RIDLE: begin
                if (replay_cmd && len != 8'd0) begin
                    txmode   <= 1'b1;
                    cfg_mode <= 1'b1;
                    tx_rptr  <= 8'd0;
                    cfg_started <= 1'b0;
                    transcode <= 1'b0;
                    st_r     <= RCFG_TX;
                end else if (transcode_cmd && tx_nexus_ok) begin
                    txmode   <= 1'b1;
                    cfg_mode <= 1'b1;
                    cfg_started <= 1'b0;
                    transcode <= 1'b1;
                    st_r     <= RCFG_TX;
                end
            end
            //start once, then wait for cfg_done to fall and rise again
            RCFG_TX: begin
                if (!cfg_started) begin
                    cfg_start <= 1'b1; cfg_started <= 1'b1; cfg_low <= 1'b0;
                end else begin
                    cfg_start <= 1'b0;
                    if (!cfg_done) cfg_low <= 1'b1;
                    if (cfg_done && cfg_low) begin
                        cfg_started <= 1'b0;
                        if (transcode) begin
                            enc_start <= 1'b1; tx_oe <= 1'b1; st_r <= RENC;
                        end else begin
                            tx_pend <= 1'b1; st_r <= RTX;
                        end
                    end
                end
            end
            RENC: begin
                enc_start <= 1'b0;
                tx_oe  <= 1'b1;
                tx_bit <= enc_active ? enc_bit : 1'b0;
                if (enc_done) begin
                    tx_oe <= 1'b0; tx_bit <= 1'b0;
                    cfg_mode <= 1'b0; cfg_started <= 1'b0; st_r <= RCFG_RX;
                end
            end
            RTX: begin
                tx_oe <= 1'b1;
                if (tx_pend) begin
                    if (tx_rptr == len) begin
                        tx_oe <= 1'b0; tx_bit <= 1'b0; tx_pend <= 1'b0;
                        cfg_mode <= 1'b0; cfg_started <= 1'b0;
                        st_r <= RCFG_RX;
                    end else begin
                        tx_cnt  <= tx_rdata[23:0];
                        tx_bit  <= tx_rdata[24];
                        tx_rptr <= tx_rptr + 1;
                            tx_pend <= (tx_rdata[23:0] == 0);
                    end
                end else if (tx_cnt == 1) begin
                    //tx_rdata already holds the next run
                    if (tx_rptr == len) begin
                        tx_oe <= 1'b0; tx_bit <= 1'b0;
                        cfg_mode <= 1'b0; cfg_started <= 1'b0;
                        st_r <= RCFG_RX;
                    end else begin
                        tx_cnt  <= tx_rdata[23:0];
                        tx_bit  <= tx_rdata[24];
                        tx_rptr <= tx_rptr + 1;
                        if (tx_rdata[23:0] == 0) tx_pend <= 1'b1;
                    end
                end else if (tx_cnt != 0) begin
                    tx_cnt <= tx_cnt - 1;
                end
            end
            RCFG_RX: begin
                if (!cfg_started) begin
                    cfg_start <= 1'b1; cfg_started <= 1'b1; cfg_low <= 1'b0;
                end else begin
                    cfg_start <= 1'b0;
                    if (!cfg_done) cfg_low <= 1'b1;
                    if (cfg_done && cfg_low) begin
                        cfg_started <= 1'b0; txmode <= 1'b0; st_r <= RIDLE;
                    end
                end
            end
            default: st_r <= RIDLE;
        endcase
    end

    reg [23:0] beat = 0;
    reg        blink = 0;
    always @(posedge clk) begin
        beat <= beat + 1'b1;
        if (beat == 0) blink <= ~blink;
    end
    //led1:0 show the retransmit state, so a stuck replay shows where
    assign led = ~{blink, txmode, truncd, pps_tick, st_r[1:0]};

endmodule
