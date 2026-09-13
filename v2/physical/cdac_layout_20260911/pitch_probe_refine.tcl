# Refine the legal pitch boundary after the coarse topology/DRC probe.
set out /repo/v2/physical/cdac_layout_20260911/probe_refine
file mkdir $out
cd $out
file copy -force /repo/v2/environment/results/physical_20260908T022855079643Z/mim_unit.mag [file join $out mim_unit.mag]

proc place_pair {direction pitch tag} {
    set cell "refine_${direction}_${tag}"
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
    set count [drc list count total]
    puts "PITCH_REFINE $direction $pitch DRC_COUNT $count"
    if {$count > 0} {
        puts "PITCH_REASONS $direction $pitch [drc listall why]"
    }
    extract all
    ext2spice lvs
    ext2spice -o ${cell}.spice
}

drc on
snap internal
foreach pitch {5.250 5.300 5.350 5.400 5.450 5.500 5.600 5.800 5.980 5.990 6.000 6.010 6.200} {
    set tag [string map {. p} $pitch]
    place_pair x $pitch $tag
}
foreach pitch {4.000 4.100 4.200 4.300 4.400 4.500 4.520 4.530 4.540 4.550 4.600 4.800 5.000 5.200 5.400 5.600} {
    set tag [string map {. p} $pitch]
    place_pair y $pitch $tag
}
quit -noprompt
