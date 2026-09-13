`timescale 1ns/1ps

// Digital control preparation only: the comparator/CDAC are external circuits.
// busy means request backpressure, not analog conversion activity.  The final
// decision period is ready, allowing completion and a new request on one edge.
module sar_controller (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [1:0]  gain_sel,
    input  wire        comparator_bit,
    output wire        ready,
    output wire        busy,
    output reg         data_valid,
    output reg  [11:0] data,
    output reg  [1:0]  data_gain,
    output reg  [1:0]  gain_latched,
    output wire        sample_en,
    output reg  [11:0] trial_code,
    output wire        comparator_evaluate
);
    localparam [1:0] IDLE = 2'd0, ACQUIRE = 2'd1, DECIDE = 2'd2;
    reg [1:0] state;
    reg [2:0] acquisition_left;
    reg [3:0] bit_index;

    wire [11:0] bit_mask = 12'b1 << bit_index;
    wire [11:0] decided_code = comparator_bit
                                  ? trial_code : (trial_code & ~bit_mask);
    wire accept = start && ready && (gain_sel != 2'b11);

    assign ready = rst_n && ((state == IDLE)
                            || ((state == DECIDE) && (bit_index == 0)));
    assign busy = !ready;
    assign sample_en = rst_n && (state == ACQUIRE);

    // This is a phase-control OUTPUT, not a clock used inside this RTL.
    // Trial changes at a rising edge; the high half allows CDAC settling and
    // comparator reset; the low half requests evaluation before the next edge.
    // Physical nonoverlap, reset time, clock skew and comparator setup time
    // require separate transistor-level timing design and verification.
    assign comparator_evaluate = rst_n && (state == DECIDE) && !clk;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            acquisition_left <= 0;
            bit_index <= 0;
            trial_code <= 0;
            gain_latched <= 0;
            data <= 0;
            data_gain <= 0;
            data_valid <= 0;
        end else begin
            data_valid <= 0;
            case (state)
                IDLE: begin
                    if (accept) begin
                        state <= ACQUIRE;
                        acquisition_left <= 4;
                        gain_latched <= gain_sel;
                        trial_code <= 0;
                    end
                end
                ACQUIRE: begin
                    if (acquisition_left == 1) begin
                        state <= DECIDE;
                        acquisition_left <= 0;
                        bit_index <= 11;
                        trial_code <= 12'h800;
                    end else begin
                        acquisition_left <= acquisition_left - 1'b1;
                    end
                end
                DECIDE: begin
                    if (bit_index == 0) begin
                        data <= decided_code;
                        data_gain <= gain_latched;
                        data_valid <= 1;
                        if (accept) begin
                            state <= ACQUIRE;
                            acquisition_left <= 4;
                            gain_latched <= gain_sel;
                            trial_code <= 0;
                        end else begin
                            state <= IDLE;
                            trial_code <= decided_code;
                        end
                    end else begin
                        bit_index <= bit_index - 1'b1;
                        trial_code <= decided_code
                                      | (12'b1 << (bit_index - 1'b1));
                    end
                end
                default: begin
                    state <= IDLE;
                    acquisition_left <= 0;
                    bit_index <= 0;
                    trial_code <= 0;
                end
            endcase
        end
    end
endmodule
