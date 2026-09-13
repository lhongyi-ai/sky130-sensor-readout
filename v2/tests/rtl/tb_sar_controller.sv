`timescale 1ns/1ps

// Self-checking digital verification; ideal held-code comparator, not ADC proof.
module tb_sar_controller;
    reg clk = 0;
    always #312.5 clk = !clk; // 1.6 MHz; full period = 625 ns.
    reg rst_n = 0;
    reg start = 0;
    reg [1:0] gain_sel = 0;
    reg [11:0] sensor_code = 0;
    reg [11:0] held_code = 0;
    wire ready, busy, data_valid, sample_en, comparator_evaluate;
    wire [11:0] data, trial_code;
    wire [1:0] data_gain, gain_latched;
    wire comparator_bit = held_code >= trial_code;

    sar_controller dut (
        .clk(clk), .rst_n(rst_n), .start(start), .gain_sel(gain_sel),
        .comparator_bit(comparator_bit), .ready(ready), .busy(busy),
        .data_valid(data_valid), .data(data), .data_gain(data_gain),
        .gain_latched(gain_latched), .sample_en(sample_en),
        .trial_code(trial_code), .comparator_evaluate(comparator_evaluate)
    );

    // Track until the acquisition-closing edge; ignore later input changes.
    always @(posedge clk or negedge rst_n)
        if (!rst_n) held_code <= 0;
        else if (sample_en) held_code <= sensor_code;

    integer cycle = 0;
    integer completed = 0;
    integer accepted = 0;
    integer ignored_busy = 0;
    integer rejected_reserved = 0;
    integer aborted = 0;
    integer back_to_back = 0;
    integer checks = 0;
    integer frame_start, frame_acq_end, frame_end;
    integer expected_bit;
    reg pending = 0;
    reg expected_valid;
    reg [11:0] expected_code = 0, expected_data = 0, expected_trial;
    reg [1:0] expected_gain = 0, expected_data_gain = 0;
    reg expected_ready, expected_sample;
    reg completing, accepting;

    task automatic check(input bit condition, input string reason);
        checks = checks + 1;
        if (!condition) begin
            $display("FAIL cycle=%0d time=%0t: %s", cycle, $time, reason);
            $fatal(1);
        end
    endtask

    // Independent schedule oracle: completion at request edge + 16, with a
    // direct final-code oracle and trial pattern computed from held input bits.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            if (pending) aborted = aborted + 1;
            pending = 0;
            expected_data = 0;
            expected_data_gain = 0;
            expected_gain = 0;
            expected_code = 0;
            #1;
            check(data_valid === 0, "reset cancels valid");
            check(data === 0 && data_gain === 0, "reset clears data metadata");
            check(sample_en === 0 && comparator_evaluate === 0,
                  "reset disables analog control requests");
            check(ready === 0 && busy === 1, "reset applies backpressure");
        end else begin
            cycle = cycle + 1;
            completing = pending && (cycle == frame_end);
            accepting = start && ready && gain_sel != 2'b11;
            expected_valid = completing;
            if (start && busy) ignored_busy = ignored_busy + 1;
            if (start && ready && gain_sel == 2'b11)
                rejected_reserved = rejected_reserved + 1;
            if (pending && sample_en) expected_code = sensor_code;
            if (completing) begin
                check(cycle - frame_start == 16, "exact 16-period latency");
                expected_data = expected_code;
                expected_data_gain = expected_gain;
                completed = completed + 1;
                pending = 0;
            end
            if (accepting) begin
                check(!pending, "request must not overwrite active conversion");
                if (completing) back_to_back = back_to_back + 1;
                accepted = accepted + 1;
                pending = 1;
                frame_start = cycle;
                frame_acq_end = cycle + 4;
                frame_end = cycle + 16;
                expected_gain = gain_sel;
                expected_code = sensor_code;
            end
            #1;
            check(data_valid === expected_valid, "valid only on completion, one cycle");
            check(data === expected_data, "data direct-code oracle and holding");
            check(data_gain === expected_data_gain, "data keeps completed-frame gain");
            check(gain_latched === expected_gain, "gain changes only on accepted start");
            expected_ready = !pending || cycle == frame_end - 1;
            expected_sample = pending && cycle < frame_acq_end;
            check(ready === expected_ready && busy === !expected_ready,
                  "ready/busy backpressure and no-bubble completion boundary");
            check(sample_en === expected_sample, "exact four full acquisition periods");
            check(comparator_evaluate === 0, "comparator resets in high clock half");
            if (pending && cycle >= frame_acq_end) begin
                expected_bit = 15 - (cycle - frame_start);
                expected_trial = (expected_code & (12'hfff << (expected_bit + 1)))
                                 | (12'b1 << expected_bit);
                check(trial_code === expected_trial,
                      "MSB-to-LSB trial keeps/rejects earlier decisions");
            end else if (pending) begin
                check(trial_code === 0, "acquisition initializes CDAC request");
            end
        end
    end

    always @(negedge clk) begin
        #1;
        if (rst_n)
            check(comparator_evaluate === (pending && cycle >= frame_acq_end),
                  "evaluation only in low halves of the 12 decision periods");
        else
            check(comparator_evaluate === 0, "reset masks evaluate even in low half");
    end

    task automatic drive_cycle(input bit request, input [1:0] gain,
                               input [11:0] value);
        @(negedge clk);
        start = request;
        gain_sel = gain;
        sensor_code = value;
        @(posedge clk);
        #2;
    endtask

    task automatic run_one(input [11:0] value, input [1:0] gain);
        integer j;
        check(!pending, "run_one begins idle");
        drive_cycle(1, gain, value);
        for (j = 0; j < 16; j = j + 1)
            drive_cycle(0, (gain + 1) % 3, value);
        check(!pending && data_valid, "run_one completed at edge + 16");
    endtask

    task automatic reset_dut;
        @(negedge clk);
        rst_n = 0;
        start = 0;
        #10;
        check(data_valid === 0 && sample_en === 0 && comparator_evaluate === 0,
              "asynchronous reset response without a rising edge");
        repeat (2) @(negedge clk);
        rst_n = 1;
        drive_cycle(0, 0, 0);
    endtask

    integer i, j, before_completed, before_accepted;
    reg [31:0] rng = 32'h54a13002;
    function automatic [31:0] advance(input [31:0] value);
        advance = {value[30:0], value[31] ^ value[21] ^ value[1] ^ value[0]};
    endfunction

    initial begin
        reset_dut();

        // Reserved gain must not start, mutate metadata or produce stale valid.
        before_accepted = accepted;
        repeat (20) drive_cycle(1, 2'b11, 12'ha55);
        check(accepted == before_accepted && !pending, "reserved gain rejected");

        // Exhaustive ideal-code conversion covers every keep/reject pattern.
        for (i = 0; i < 4096; i = i + 1)
            run_one(i[11:0], i % 3);

        // Hold start high with adversarial gain/input changes while busy.
        // Every completion edge simultaneously accepts the following frame.
        before_completed = completed;
        before_accepted = accepted;
        drive_cycle(1, 0, 12'h000);
        for (i = 0; i < 32 * 16; i = i + 1)
            drive_cycle(1, (i / 16 + 1) % 3, (i * 137) % 4096);
        check(completed - before_completed == 32, "100 kS/s sustained throughput");
        check(accepted - before_accepted == 33, "completion accepts next frame");
        while (pending) drive_cycle(0, 2'b11, 12'hfff);

        // Pseudo-random requests, reserved gains and changing input, deterministic.
        for (i = 0; i < 4096; i = i + 1) begin
            rng = advance(rng);
            drive_cycle(rng[0], rng[2:1], rng[14:3]);
        end
        while (pending) drive_cycle(0, 0, 12'h7ff);

        // Abort in every acquisition/decision period, including final decision.
        for (i = 0; i < 16; i = i + 1) begin
            drive_cycle(1, i % 3, (i * 271) % 4096);
            for (j = 0; j < i; j = j + 1)
                drive_cycle(0, 2'b11, (i * 271) % 4096);
            reset_dut();
            repeat (18) drive_cycle(0, 0, 12'h123);
            check(!pending && data_valid === 0, "aborted conversion never reappears");
            run_one(12'h55a, 2'b01);
        end

        // Reserved gain at completion rejects only next frame, not old result.
        drive_cycle(1, 2'b10, 12'habc);
        for (i = 0; i < 16; i = i + 1)
            drive_cycle(1, 2'b11, 12'habc);
        check(data === 12'habc && data_gain === 2'b10 && !pending,
              "reserved boundary request preserves previous completion");
        drive_cycle(0, 0, 0);
        check(data_valid === 0, "valid clears without requiring another start");
        check(accepted == completed + aborted, "every accepted frame completes or aborts");
        check(ignored_busy > 0 && rejected_reserved > 0 && back_to_back >= 32,
              "required request corner cases actually exercised");
        $display("PASS sar_controller: checks=%0d accepted=%0d completed=%0d aborted=%0d ignored_busy=%0d reserved_rejected=%0d back_to_back=%0d",
                 checks, accepted, completed, aborted, ignored_busy,
                 rejected_reserved, back_to_back);
        $finish;
    end

    initial begin
        #100000000;
        $fatal(1, "FAIL: simulation watchdog expired");
    end
endmodule
