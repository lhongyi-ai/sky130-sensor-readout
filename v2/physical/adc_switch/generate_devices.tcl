# Generate the frozen sampling-TG transistor geometries using PDK PCells.
set out /repo/v2/physical/adc_switch/results
file mkdir $out
cd $out
drc off
snap internal
load tg_nfet8
set np [dict merge [sky130::sky130_fd_pr__nfet_01v8_defaults] {w 8 l 0.15 nf 1 guard 1}]
puts "NFET_BBOX [sky130::sky130_fd_pr__nfet_01v8_draw $np]"
save tg_nfet8
load tg_pfet16
set pp [dict merge [sky130::sky130_fd_pr__pfet_01v8_defaults] {w 16 l 0.15 nf 1 guard 1}]
puts "PFET_BBOX [sky130::sky130_fd_pr__pfet_01v8_draw $pp]"
save tg_pfet16
quit -noprompt
