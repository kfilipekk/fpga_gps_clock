//configures the cc1101 over spi at power up, mode 0
`default_nettype none

module spi_cfg #(
    parameter DIV    = 8,
    parameter SETTLE = 54000,   //crystal settle, 2 ms
    parameter N      = 27,
    parameter [7:0] IOCFG0_RX = 8'h0D, //0x3f puts xtal/192 on gdo0
    parameter [23:0] FREQ = 24'h10B071 //433.92 on an exact 26 mhz xtal
) (
    input  wire clk,
    output reg  sck  = 1'b0,
    output reg  mosi = 1'b0,
    input  wire miso,
    output reg  csn  = 1'b1,
    output reg  done = 1'b0,
    input  wire mode,
    input  wire start
);

    //{addr, value}
    function [15:0] cfgrom(input [4:0] i, input m);
        case (i)
            5'd0:  cfgrom = m ? 16'h022E : {8'h02, IOCFG0_RX}; //iocfg0
            5'd1:  cfgrom = 16'h0347; //fifothr
            5'd2:  cfgrom = 16'h0830; //pktctrl0 async serial, no crc
            5'd3:  cfgrom = 16'h0B06; //fsctrl1
            5'd4:  cfgrom = {8'h0D, FREQ[23:16]}; //freq2
            5'd5:  cfgrom = {8'h0E, FREQ[15:8]}; //freq1
            5'd6:  cfgrom = {8'h0F, FREQ[7:0]}; //freq0
            5'd7:  cfgrom = 16'h1087; //mdmcfg4 rx bandwidth
            5'd8:  cfgrom = 16'h1100; //mdmcfg3
            5'd9:  cfgrom = 16'h1230; //mdmcfg2 ask/ook, no sync
            5'd10: cfgrom = 16'h1322; //mdmcfg1
            5'd11: cfgrom = 16'h14F8; //mdmcfg0
            5'd12: cfgrom = 16'h1818; //mcsm0 autocal idle->rx
            5'd13: cfgrom = 16'h1916; //foccfg
            5'd14: cfgrom = 16'h1B43; //agcctrl2
            5'd15: cfgrom = 16'h1C40; //agcctrl1
            5'd16: cfgrom = 16'h1D93; //agcctrl0, 16 db ook boundary
            5'd17: cfgrom = 16'h20FB; //worctrl
            5'd18: cfgrom = 16'h2156; //frend1
            5'd19: cfgrom = 16'h2211; //frend0
            5'd20: cfgrom = 16'h23E9; //fscal3
            5'd21: cfgrom = 16'h242A; //fscal2
            5'd22: cfgrom = 16'h2500; //fscal1
            5'd23: cfgrom = 16'h261F; //fscal0
            5'd24: cfgrom = 16'h2C81; //test2
            5'd25: cfgrom = 16'h2D35; //test1
            5'd26: cfgrom = 16'h2E09; //test0
            default: cfgrom = 16'h0000;
        endcase
    endfunction

    //sres, the writes, then sidle, sfrx and srx or stx
    function [7:0] txbyte(input [5:0] t, input b, input m);
        reg [15:0] w;
        begin
            w = cfgrom(t[4:0] - 5'd1, m);
            if      (t == 6'd0)   txbyte = 8'h30;             //sres
            else if (t <= N)      txbyte = b ? w[7:0] : w[15:8];
            else if (t == N + 1)  txbyte = 8'h36;             //sidle
            else if (t == N + 2)  txbyte = 8'h3A;             //sfrx (flush)
            else                  txbyte = m ? 8'h35 : 8'h34; //stx / srx
        end
    endfunction

    function twobyte(input [5:0] t);
        twobyte = (t >= 6'd1) && (t <= N);
    endfunction

    localparam TXN = N + 4;

    reg [1:0] ms = 2'b11;
    always @(posedge clk) ms <= {ms[0], miso};

    localparam POR=3'd0, CSLO=3'd1, RDY=3'd2, SHIFT=3'd3, CSHI=3'd4, DN=3'd5;
    reg [2:0]  st   = POR;
    reg [15:0] dc   = 0;
    reg [2:0]  bcnt = 0;
    reg [7:0]  sr   = 0;
    reg        bsel = 0;
    reg [5:0]  txn  = 0;

    always @(posedge clk) begin
        case (st)
            POR: begin
                csn <= 1'b1; sck <= 1'b0;
                if (dc == SETTLE) begin dc <= 0; st <= CSLO; end
                else dc <= dc + 1'b1;
            end
            CSLO: begin csn <= 1'b0; dc <= 0; st <= RDY; end
            RDY: begin                       //so low, chip ready
                if (ms[1] == 1'b0 || dc == 16'd6000) begin
                    sr <= txbyte(txn, 1'b0, mode); bsel <= 1'b0;
                    bcnt <= 3'd7; sck <= 1'b0; dc <= 0; st <= SHIFT;
                end else dc <= dc + 1'b1;
            end
            SHIFT: begin
                mosi <= sr[7];
                if (dc == DIV - 1) begin
                    dc  <= 0;
                    sck <= ~sck;
                    if (sck) begin           //falling edge
                        if (bcnt == 3'd0) begin
                            if (twobyte(txn) && !bsel) begin
                                sr <= txbyte(txn, 1'b1, mode); bsel <= 1'b1;
                                bcnt <= 3'd7;
                            end else begin st <= CSHI; dc <= 0; end
                        end else begin
                            sr <= {sr[6:0], 1'b0}; bcnt <= bcnt - 3'd1;
                        end
                    end
                end else dc <= dc + 1'b1;
            end
            CSHI: begin
                csn <= 1'b1; sck <= 1'b0;
                if (dc == DIV * 2) begin
                    dc <= 0;
                    if (txn == TXN - 1) st <= DN;
                    else begin txn <= txn + 6'd1; st <= CSLO; end
                end else dc <= dc + 1'b1;
            end
            DN: begin
                done <= 1'b1;
                if (start) begin
                    done <= 1'b0; txn <= 0; bsel <= 1'b0; st <= CSLO;
                end
            end
            default: st <= POR;
        endcase
    end

`ifdef FORMAL
    //per-state invariants so induction starts from reachable states
    always @* begin
        assert (st <= DN && txn < TXN);
        if (st != SHIFT) assert (!sck);
        if (st == POR)   assert (csn && dc <= SETTLE);
        if (st == CSLO || st == DN) assert (csn);
        if (st == RDY)   assert (!csn && dc <= 16'd6000);
        if (st == SHIFT) assert (!csn && dc < DIV && (sck || dc != 0 ? mosi == sr[7] : 1'b1));
        if (st == CSHI)  assert (dc <= DIV * 2);
        if (done)        assert (st == DN);
    end
`endif
endmodule
