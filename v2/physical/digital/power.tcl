set run $::env(SAR_PHYSICAL_RUN_DIR)
read_liberty "$::env(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
read_verilog "$run/final/nl/sar_controller.nl.v"
link_design sar_controller
read_sdc v2/digital/constraints.sdc
set_propagated_clock [all_clocks]
read_spef "$run/final/spef/nom/sar_controller.nom.spef"
read_vcd -scope tb_sar_controller/dut v2/physical/digital/results/routed_activity.vcd
puts "EVIDENCE: TT25C1.8V cell-library power with nominal routed RC and zero-delay exhaustive-test activity"
puts "LIMITATION: not transistor dynamic current, not analog power, not glitch-accurate or workload-independent"
report_activity_annotation -report_unannotated
report_power -digits 6
report_net comparator_bit
exit
