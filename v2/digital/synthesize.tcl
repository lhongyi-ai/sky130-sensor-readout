# Run from the project root with Yosys: yosys -c v2/digital/synthesize.tcl
# Native source RTL and its interface are intentionally unchanged.
yosys -import
set library "$::env(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
read_liberty -lib $library
read_verilog v2/rtl/sar_controller.v
hierarchy -check -top sar_controller
synth -top sar_controller -flatten
dfflibmap -liberty $library
abc -liberty $library
clean
check -assert
tee -o v2/digital/results/synthesis_stats.txt stat -liberty $library
tee -o v2/digital/results/synthesis_stats.json stat -json -liberty $library
write_verilog -noattr -noexpr v2/digital/results/sar_controller_mapped.v
write_json v2/digital/results/sar_controller_mapped.json
