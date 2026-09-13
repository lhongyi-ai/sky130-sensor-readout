# Flatten and extract the complete differential CDAC interconnect RC network.
set out /repo/v2/physical/cdac_route_20260911/artifacts
cd $out
file delete -force [file join $out cdac_diff_routed_flat_rc.mag]
file delete -force [file join $out cdac_diff_routed_flat_rc.ext]

load cdac_diff_routed
select top cell
expand
flatten cdac_diff_routed_flat_rc
load cdac_diff_routed_flat_rc
save cdac_diff_routed_flat_rc
select top cell
expand
extract all
extresist threshold 0
extresist minres 0
extresist mindelay 0
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o cdac_diff_routed_flat_rc.spice
puts "TOP_RC_EXTRACTION_DONE cdac_diff_routed_flat_rc"
quit -noprompt
