//latches the taps on the edge and shifts them out counting ones
`default_nettype none

module tdc_core #(
    parameter N = 1200
) (
    input  wire         clk,
    input  wire         trig,
    input  wire [N-1:0] taps,
    output reg  [11:0]  fine,
    output reg          valid
);

    localparam [11:0] NN = N;

    reg [N-1:0] snap  = 0;
    reg         armed = 1'b0;
    reg         t1    = 1'b0;
    reg         t2    = 1'b0;
    reg         busy  = 1'b0;
    reg [11:0]  left  = 0;
    reg [11:0]  count = 0;

    initial begin
        fine  = 0;
        valid = 1'b0;
    end

    always @(posedge clk) begin
        valid <= 1'b0;
        t1    <= trig;
        t2    <= t1;
        if (busy) begin
            snap  <= snap >> 1;
            count <= count + {11'b0, snap[0]};
            left  <= left - 12'd1;
            if (left == 12'd1) begin
                fine  <= count + {11'b0, snap[0]};
                valid <= 1'b1;
                busy  <= 1'b0;
            end
        end else if (t1 && !t2 && armed) begin
            //snap still holds the vector from the edge
            busy  <= 1'b1;
            armed <= 1'b0;
            left  <= NN;
            count <= 12'd0;
        end else begin
            snap  <= taps;
            armed <= 1'b1;
        end
    end

endmodule
