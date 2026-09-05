//spi mode 0 for any miso, mode and start: sck low while csn is high
`default_nettype none

module spi_cfg_f (
    input wire clk,
    input wire miso,
    input wire mode,
    input wire start
);
    wire sck, mosi, csn, done;
    spi_cfg #(.DIV(2), .SETTLE(5), .N(3)) dut (
        .clk(clk), .sck(sck), .mosi(mosi), .miso(miso), .csn(csn),
        .done(done), .mode(mode), .start(start)
    );

    reg past_ok = 1'b0;
    always @(posedge clk) past_ok <= 1'b1;

    always @(posedge clk) begin
        assert (!(csn && sck));
        assert (!done || csn);
        if (past_ok && sck && !$past(sck))
            assert (mosi == $past(mosi));
        cover (past_ok && csn && !$past(csn));    //a whole transaction
    end
endmodule
