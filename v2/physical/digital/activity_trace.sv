// Attach to the unchanged exhaustive functional TB. This records zero-delay
// gate activity, not analog activity or delay-dependent glitch power.
module activity_trace;
    initial begin
        $dumpfile("v2/physical/digital/results/routed_activity.vcd");
        $dumpvars(0, tb_sar_controller.dut);
    end
endmodule
