# Fresh-process RC extraction for the representative routed tile.
# Running extresist in the generation process retains the hierarchical
# extraction root and cannot find the flattened parents; this separate entry
# point is intentional and mirrors the full-array extraction flow.
set out /repo/v2/physical/cdac_route_20260911/probe_artifacts
cd $out
load cdac_route_probe_flat
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
ext2spice -o cdac_route_probe_flat.rc.spice
puts "PROBE_RC_EXTRACTION_DONE cdac_route_probe_flat"
quit -noprompt
