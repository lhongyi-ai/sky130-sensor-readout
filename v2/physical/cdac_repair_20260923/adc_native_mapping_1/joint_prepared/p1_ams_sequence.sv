`timescale 1ns/1ps

// No ideal comparator and no expected ADC conversion codes exist here.
// Expected data is assembled solely from Q/QB observed at actual decision edges.
module p1_ams_sequence(
  output reg clk=0, output reg rst_n=0, output reg start=0,
  output reg [1:0] gain_sel=0, output reg [1:0] stimulus_sel=0,
  input wire ready, busy, data_valid, sample_en, comparator_evaluate,
  input wire [11:0] data, trial_code,
  input wire [1:0] data_gain, gain_latched,
  input wire cmp_q, cmp_qb, cmp_q_valid, cmp_qb_valid,
  input wire [11:0] trial_fb, trial_fb_valid,
  input wire sample_fb, sample_fb_valid, eval_fb, eval_fb_valid
);
  always #312.5 clk=~clk;
  integer cycle=0, accepted=0, completed=0, captures=0, checked=0;
  integer ignored_busy=0, reserved=0, frame_start=0, age=0;
  reg pending=0, completing=0, accepting=0;
  reg [11:0] observed_word=0, wanted_data=0, wanted_trial=0;
  reg [1:0] frame_gain=0, wanted_data_gain=0, wanted_gain=0;
  reg wanted_valid=0;
  integer fd;
  initial begin
    fd=$fopen("ams_decisions.csv","w");
    if (!fd) begin $display("P1_AMS_FAIL Cannot create decision evidence"); $finish; end
    $fdisplay(fd,"time_ns,frame,decision,trial_word,q,qb,gain");
  end
  task automatic check;
    input condition;
    input [2047:0] message;
    begin
    checked=checked+1;
    if (condition !== 1'b1) begin $display("P1_AMS_FAIL cycle=%0d time=%0t %s",cycle,$time,message); $finish; end
    end
  endtask

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pending=0; wanted_data=0; wanted_data_gain=0; wanted_gain=0;
      observed_word=0; captures=0;
      #5;
      check(data_valid===0 && data===0 && data_gain===0,"reset clears completed data");
      check(ready===0 && busy===1,"reset backpressure");
      check(sample_en===0 && comparator_evaluate===0,"reset masks requests");
    end else begin
      cycle=cycle+1;
      age=cycle-frame_start;
      completing=pending && age==16;
      accepting=start && ready && gain_sel!=2'b11;
      wanted_valid=completing;
      if(start && busy) ignored_busy=ignored_busy+1;
      if(start && ready && gain_sel==2'b11) reserved=reserved+1;

      // The first decision is consumed five edges after acceptance.
      if(pending && age>=5 && age<=16) begin
        check(cmp_q_valid===1 && cmp_qb_valid===1,"real comparator rails valid at read");
        check((cmp_q ^ cmp_qb)===1,"real Q/QB complement at read");
        wanted_trial=(observed_word << (12-captures)) | (12'b1 << (11-captures));
        check(trial_code===wanted_trial,"trial sequence follows previous actual decisions");
        check(trial_fb_valid===12'hfff && trial_fb===trial_code,"electrical trial bus at decision");
        $fdisplay(fd,"%0.3f,%0d,%0d,%0d,%0d,%0d,%0d",$realtime,accepted,captures,
                  trial_fb,cmp_q,cmp_qb,frame_gain);
        observed_word={observed_word[10:0],cmp_q};
        captures=captures+1;
      end
      if(completing) begin
        check(captures==12,"twelve actual comparator decisions");
        wanted_data=observed_word; wanted_data_gain=frame_gain;
        pending=0; completed=completed+1;
      end
      if(accepting) begin
        check(!pending,"busy request cannot replace a frame");
        pending=1; frame_start=cycle; accepted=accepted+1;
        frame_gain=gain_sel; wanted_gain=gain_sel;
        observed_word=0; captures=0;
      end
      #5;
      check(data_valid===wanted_valid,"valid has exact sixteen-period latency");
      check(data===wanted_data,"output equals actual analog decision word");
      check(data_gain===wanted_data_gain,"completed output retains its own gain");
      check(gain_latched===wanted_gain,"gain latch accepts only authorized request");
      check(ready===( !pending || cycle-frame_start==15),"ready at final-decision boundary");
      check(busy===!ready,"ready/busy complement");
      check(sample_en===(pending && cycle-frame_start<4),"four acquisition periods");
      check(comparator_evaluate===0,"evaluation reset during high clock half");
      check(trial_fb_valid===12'hfff && trial_fb===trial_code,"electrical trial bus settled");
      check(sample_fb_valid===1 && sample_fb===sample_en,"sample command electrical roundtrip");
      check(eval_fb_valid===1 && eval_fb===comparator_evaluate,"eval command electrical roundtrip");
      if(completing)
        $display("P1_AMS_FRAME time_ns=%0.3f data=%0d data_gain=%0d new_gain=%0d",
                 $realtime,data,data_gain,gain_latched);
    end
  end

  task automatic drive;
    input request;
    input [1:0] gain;
    input [1:0] stimulus;
    begin
    @(negedge clk); #10;
    start=request;gain_sel=gain;stimulus_sel=stimulus;
    @(posedge clk); #10;
    end
  endtask
  integer i;
  initial begin
    repeat(3) @(negedge clk);
    #10; rst_n=1;
    drive(1,2'b11,0); drive(0,0,0);  // Reserved request must not launch.
    drive(1,0,0);                     // First request: negative input, gain 0.
    for(i=0;i<15;i=i+1)
      drive(1,(i%3),i<6 ? 0 : 1);    // Busy requests ignored, input changes after acquisition.
    drive(1,2,1);                     // Complete old frame and accept gain 2 together.
    for(i=0;i<16;i=i+1) drive(0,(i%3),1);
    check(completed==2 && accepted==2 && !pending,"two complete continuous real-analog frames");
    drive(0,0,1);
    check(data_valid===0 && ignored_busy>0 && reserved>0,"valid clearing and boundary coverage");
    $fclose(fd);
    $display("P1_AMS_INTERFACE_SMOKE_PASS frames=%0d checks=%0d ignored_busy=%0d reserved=%0d",
             completed,checked,ignored_busy,reserved);
    $finish;
  end
  initial begin
    #100000;
    $display("P1_AMS_FAIL watchdog 100us"); $finish;
  end
endmodule
