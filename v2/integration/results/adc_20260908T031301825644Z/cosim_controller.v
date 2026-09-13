`timescale 1ns/1ps
// Port vector order follows ngspice d_cosim MSB-first mapping.
// The existing synthesizable SAR is used unchanged. This wrapper only exposes
// ports and writes testbench result records; it is not an analog replacement.
module cosim_controller(input wire [5:0] digital_inputs,
                        output wire [32:0] digital_outputs);
    wire clk = digital_inputs[5];
    wire rst_n = digital_inputs[4];
    wire start = digital_inputs[3];
    wire [1:0] gain_sel = digital_inputs[2:1];
    wire comparator_bit = digital_inputs[0];
    wire ready, busy, data_valid, sample_en, comparator_evaluate;
    wire [11:0] data, trial_code;
    wire [1:0] data_gain, gain_latched;
    sar_controller dut(.clk(clk), .rst_n(rst_n), .start(start), .gain_sel(gain_sel),
        .comparator_bit(comparator_bit), .ready(ready), .busy(busy),
        .data_valid(data_valid), .data(data), .data_gain(data_gain),
        .gain_latched(gain_latched), .sample_en(sample_en),
        .trial_code(trial_code), .comparator_evaluate(comparator_evaluate));
    assign digital_outputs = {ready, busy, data_valid, data, data_gain,
                              gain_latched, sample_en, trial_code, comparator_evaluate};
    always @(posedge data_valid)
        $display("COSIM_RESULT time_ns=%0.3f code=%0d gain_code=%0d", $realtime, data, data_gain);
endmodule
