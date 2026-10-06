`timescale 1ns/1ps
`include "profile.vh"

// Scoreboard only. No comparator model or prerecorded comparison is present.
module p2_sequence(
  output reg clk=0, output reg rst_n=0, output reg start=0,
  output reg [1:0] gain_sel=0, output reg [3:0] stimulus_sel=0,
  input wire ready, busy, data_valid, sample_en, comparator_evaluate,
  input wire [11:0] data, trial_code,
  input wire [1:0] data_gain, gain_latched,
  input wire cmp_q, cmp_qb, cmp_q_valid, cmp_qb_valid,
  input wire [11:0] trial_fb, trial_fb_valid,
  input wire sample_fb, sample_fb_valid, eval_fb, eval_fb_valid,
  input wire reset_fb, reset_fb_valid
);
  always #312.5 clk=~clk;
  integer cycle=0, accepted=0, completed=0, captures=0, checks=0;
  integer ignored_busy=0, reserved=0, aborted=0, frame_start=0, age=0;
  integer frame_id=0, active_stimulus=0, finished_frame=0, finished_stimulus=0;
  reg pending=0, completing=0, accepting=0;
  reg [11:0] observed_word=0, wanted_data=0, wanted_trial=0;
  reg [1:0] frame_gain=0, wanted_data_gain=0, wanted_gain=0;
  reg wanted_valid=0;
  integer decisions_fd, events_fd, frames_fd;
  initial begin
    decisions_fd=$fopen("decisions.csv","w");
    events_fd=$fopen("events.csv","w");
    frames_fd=$fopen("frames.csv","w");
    if(!decisions_fd || !events_fd || !frames_fd) begin $display("P2_FAIL evidence file creation"); $finish; end
    $fdisplay(decisions_fd,"time_ns,frame,decision,trial_word,q,qb,gain,stimulus");
    $fdisplay(events_fd,"time_ns,event,frame,gain,stimulus");
    $fdisplay(frames_fd,"time_ns,frame,data,data_gain,new_gain,stimulus");
  end
  task automatic check;
    input condition;
    input [2047:0] message;
    begin
      checks=checks+1;
      if(condition !== 1'b1) begin $display("P2_FAIL cycle=%0d time=%0t %s",cycle,$time,message); $finish; end
    end
  endtask
  always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
      if(pending) begin
        aborted=aborted+1;
        $fdisplay(events_fd,"%0.3f,abort,%0d,%0d,%0d",$realtime,frame_id,frame_gain,active_stimulus);
      end
      pending=0; wanted_data=0; wanted_data_gain=0; wanted_gain=0;
      observed_word=0; captures=0;
      #5;
      check(data_valid===0 && data===0 && data_gain===0,"reset clears completed data");
      check(ready===0 && busy===1,"reset backpressure");
      check(sample_en===0 && comparator_evaluate===0,"reset masks requests");
      check(reset_fb_valid===1 && reset_fb===0,"actual electrical reset asserted");
    end else begin
      cycle=cycle+1;
      age=cycle-frame_start;
      completing=pending && age==16;
      accepting=start && ready && gain_sel!=2'b11;
      wanted_valid=completing;
      if(start && busy) ignored_busy=ignored_busy+1;
      if(start && ready && gain_sel==2'b11) begin
        reserved=reserved+1;
        $fdisplay(events_fd,"%0.3f,reserved,%0d,%0d,%0d",$realtime,frame_id,gain_sel,stimulus_sel);
      end
      if(pending && age==4)
        $fdisplay(events_fd,"%0.3f,acquisition_end,%0d,%0d,%0d",$realtime,frame_id,frame_gain,active_stimulus);
      if(pending && age>=5 && age<=16) begin
        check(cmp_q_valid===1 && cmp_qb_valid===1,"real comparator rails valid at read");
        check((cmp_q ^ cmp_qb)===1,"real Q/QB complement at read");
        wanted_trial=(observed_word << (12-captures)) | (12'b1 << (11-captures));
        check(trial_code===wanted_trial,"trial follows previous actual decisions");
        check(trial_fb_valid===12'hfff && trial_fb===trial_code,"electrical trial bus at capture");
        $fdisplay(decisions_fd,"%0.3f,%0d,%0d,%0d,%0d,%0d,%0d,%0d",$realtime,frame_id,
                  captures,trial_fb,cmp_q,cmp_qb,frame_gain,active_stimulus);
        observed_word={observed_word[10:0],cmp_q}; captures=captures+1;
      end
      if(completing) begin
        check(captures==12,"twelve actual comparator decisions");
        wanted_data=observed_word; wanted_data_gain=frame_gain;
        pending=0; completed=completed+1;
        // Capture old metadata before accepting a new frame at the same edge.
        finished_frame=frame_id; finished_stimulus=active_stimulus;
      end
      if(accepting) begin
        check(!pending,"busy request cannot replace a frame");
        pending=1; frame_start=cycle; accepted=accepted+1; frame_id=accepted;
        frame_gain=gain_sel; wanted_gain=gain_sel; active_stimulus=stimulus_sel;
        observed_word=0; captures=0;
        $fdisplay(events_fd,"%0.3f,accept,%0d,%0d,%0d",$realtime,frame_id,frame_gain,active_stimulus);
      end
      #5;
      check(data_valid===wanted_valid,"valid exact sixteen-period latency");
      check(data===wanted_data,"output equals actual analog decision word");
      check(data_gain===wanted_data_gain,"completed word retains its own gain");
      check(gain_latched===wanted_gain,"gain changes only on accepted request");
      check(ready===(!pending || cycle-frame_start==15),"ready at final-decision boundary");
      check(busy===!ready,"ready/busy complement");
      check(sample_en===(pending && cycle-frame_start<4),"four acquisition periods");
      check(comparator_evaluate===0,"evaluation resets in high clock half");
      check(trial_fb_valid===12'hfff && trial_fb===trial_code,"electrical trial settled");
      check(sample_fb_valid===1 && sample_fb===sample_en,"sample electrical roundtrip");
      check(eval_fb_valid===1 && eval_fb===comparator_evaluate,"eval electrical roundtrip");
      check(reset_fb_valid===1 && reset_fb===1,"actual electrical reset released");
      if(completing) begin
        $fdisplay(frames_fd,"%0.3f,%0d,%0d,%0d,%0d,%0d",$realtime,finished_frame,data,data_gain,gain_latched,finished_stimulus);
        $display("P2_FRAME time_ns=%0.3f data=%0d data_gain=%0d new_gain=%0d",$realtime,data,data_gain,gain_latched);
      end
    end
  end
  task automatic drive;
    input request;
    input [1:0] gain;
    input [3:0] stimulus;
    begin
      @(negedge clk); #10; start=request; gain_sel=gain; stimulus_sel=stimulus;
      @(posedge clk); #10;
    end
  endtask
  integer i,f;
  initial begin
    repeat(3) @(negedge clk); #10;
    $fdisplay(events_fd,"%0.3f,reset_release,0,0,0",$realtime);
    rst_n=1;
    drive(1,2'b11,0); drive(0,0,0);
    drive(1,0,0);
    for(f=0;f<`P2_FRAMES;f=f+1) begin
      for(i=0;i<15;i=i+1)
        drive(1,i%3,(i<6 || f==`P2_FRAMES-1)?f:f+1);
      if(f<`P2_FRAMES-1) drive(1, (`P2_FRAMES==2)?2:(f+1)%3, f+1);
      else drive(0,0,f);
    end
    check(completed==`P2_FRAMES && accepted==`P2_FRAMES && !pending,"requested continuous real-analog frames");
    drive(0,0,`P2_FRAMES-1);
    check(data_valid===0 && ignored_busy>0 && reserved>0,"valid clears; busy/reserved coverage");
    // Independent abort: begin another real conversion, assert reset during EVAL.
    drive(1,1,`P2_FRAMES-1);
    repeat(4) drive(0,0,`P2_FRAMES-1);
    @(negedge clk); #100;
    check(comparator_evaluate===1,"reset-abort occurs during real evaluation");
    $fdisplay(events_fd,"%0.3f,reset_assert,%0d,%0d,%0d",$realtime,frame_id,frame_gain,active_stimulus);
    rst_n=0; start=0;
    #100;
    check(cmp_q_valid===1 && cmp_qb_valid===1 && cmp_q===0 && cmp_qb===1,"analog reset determines Q0/QB1");
    $fdisplay(events_fd,"%0.3f,reset_hold,%0d,%0d,%0d",$realtime,frame_id,frame_gain,active_stimulus);
    repeat(2) @(negedge clk); #10;
    rst_n=1;
    $fdisplay(events_fd,"%0.3f,reset_release,%0d,%0d,%0d",$realtime,frame_id,frame_gain,active_stimulus);
    repeat(2) drive(0,0,`P2_FRAMES-1);
    check(completed==`P2_FRAMES && aborted==1 && !pending && data_valid===0,"aborted conversion never emits data");
    $fclose(decisions_fd); $fclose(events_fd); $fclose(frames_fd);
    $display("P2_HANDSHAKE_PASS frames=%0d accepted=%0d aborted=%0d checks=%0d ignored_busy=%0d reserved=%0d",
             completed,accepted,aborted,checks,ignored_busy,reserved);
    $finish;
  end
  initial begin
    #(`P2_FRAMES*10000+19000);
    $display("P2_FAIL bounded simulated-time watchdog"); $finish;
  end
endmodule
