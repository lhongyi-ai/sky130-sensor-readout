# Measure legal placement pitch for the exact 3 um x 3 um SKY130 MIM PCell.
# This is a geometry/topology probe only; it does not route a CDAC.
set out /repo/v2/physical/cdac_layout_20260911/probe_artifacts
file mkdir $out
cd $out
file copy -force /repo/v2/environment/results/physical_20260908T022855079643Z/mim_unit.mag [file join $out mim_unit.mag]

proc place_pair {direction pitch tag} {
    set cell "probe_${direction}_${tag}"
    load $cell -silent
    box values 0 0 0 0
    getcell mim_unit child 0 0 parent 0um 0um
    identify X0
    if {$direction eq "x"} {
        getcell mim_unit child 0 0 parent ${pitch}um 0um
    } else {
        getcell mim_unit child 0 0 parent 0um ${pitch}um
    }
    identify X1
    save $cell
    select top cell
    expand
    drc check
    drc catchup
    puts "PITCH_PROBE $direction $pitch DRC_COUNT [drc list count total] BBOX [box values]"
    extract all
    ext2spice lvs
    ext2spice -o ${cell}.spice
}

drc on
snap internal
foreach pitch {4.000 4.800 5.000 5.100 5.150 5.160 5.170 5.180 5.200 5.250} {
    set tag [string map {. p} $pitch]
    place_pair x $pitch $tag
}
foreach pitch {3.400 3.500 3.600 3.700 3.800 3.900 4.000} {
    set tag [string map {. p} $pitch]
    place_pair y $pitch $tag
}
quit -noprompt
