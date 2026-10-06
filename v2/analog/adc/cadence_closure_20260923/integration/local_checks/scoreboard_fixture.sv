`timescale 1ns/1ps
// SYNTHETIC SCOREBOARD UNIT TEST ONLY. Never an ADC, never AMS input.
module scoreboard_fixture;
 wire clk,rst_n,start,ready,busy,data_valid,sample_en,comparator_evaluate;
 wire [1:0] gain_sel,data_gain,gain_latched;
 wire [3:0] stimulus_sel;
 wire [11:0] data,trial_code;
 reg q=0;
 always @(negedge clk or negedge rst_n) begin
   if(!rst_n) q=0;
   else begin #2; if(comparator_evaluate) q=~q; end
 end
 sar_controller dut(.*,.comparator_bit(q));
 `ifdef BAD_GAIN
 wire [1:0] observed_gain=data_valid?gain_latched:data_gain;
 `else
 wire [1:0] observed_gain=data_gain;
 `endif
 `ifdef BAD_RAIL
 wire valid=0;
 `else
 wire valid=1;
 `endif
 p2_sequence seq(.*,.data_gain(observed_gain),.cmp_q(q),.cmp_qb(~q),
 .cmp_q_valid(valid),.cmp_qb_valid(valid),.trial_fb(trial_code),.trial_fb_valid(12'hfff),
 .sample_fb(sample_en),.sample_fb_valid(1'b1),.eval_fb(comparator_evaluate),.eval_fb_valid(1'b1),
 .reset_fb(rst_n),.reset_fb_valid(1'b1));
endmodule
