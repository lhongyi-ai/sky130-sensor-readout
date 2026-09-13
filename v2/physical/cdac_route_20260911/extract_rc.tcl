# Full interconnect RC extraction for the already-flattened routed CDAC sides.
# Run in a fresh Magic process so extresist has one unambiguous root at a time.
set out /repo/v2/physical/cdac_route_20260911/artifacts
cd $out

foreach polarity {p n} {
    set cell cdac_side_${polarity}_routed_flat
    load $cell
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
    ext2spice -o ${cell}.rc.spice
    puts "RC_EXTRACTION_DONE $cell"
}
quit -noprompt
