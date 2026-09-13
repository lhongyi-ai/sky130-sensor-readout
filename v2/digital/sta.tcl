set library "$::env(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/$::env(SAR_LIBERTY)"
read_liberty $library
read_verilog v2/digital/results/sar_controller_mapped.v
link_design sar_controller
read_sdc v2/digital/constraints.sdc
puts "EVIDENCE: library-cell STA; no placed/routed wire parasitics"
puts "LIBERTY: $library"
report_units
check_setup -verbose
report_checks -path_delay max -group_path_count 10 -format full_clock_expanded
report_checks -path_delay min -group_path_count 10 -format full_clock_expanded
report_checks -from [get_ports clk] -to [get_ports comparator_evaluate] -path_delay max
report_worst_slack -max
report_worst_slack -min
report_check_types -max_slew -max_capacitance -max_fanout -violators
exit
