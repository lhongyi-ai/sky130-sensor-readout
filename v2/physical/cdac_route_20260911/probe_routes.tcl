# SKY130 routing probe for the differential CDAC work.
#
# This deliberately small cell proves the real MIM terminal access pattern
# before the 8k-unit generator is allowed to create a large layout.  C2 is
# tied on metal3 to TOP.  C1 is lifted from metal4 to metal5 with real via4
# geometry and routed into two switched capacitor banks.

set out /repo/v2/physical/cdac_route_20260911/probe_artifacts
file mkdir $out
cd $out
foreach cell {cdac_route_probe cdac_route_probe_flat} {
    foreach suffix {mag ext gds} {file delete -force [file join $out ${cell}.${suffix}]}
}
file copy -force /repo/v2/physical/cdac_layout_20260911/artifacts/mim_unit.mag [file join $out mim_unit.mag]

snap internal
drc off

proc rectangle {layer x1 y1 x2 y2} {
    box values ${x1}um ${y1}um ${x2}um ${y2}um
    paint $layer
}

proc via45 {x y} {
    # via4's Magic contact tile must be at least 1.18 um square.  The M5
    # landing is widened to the 1.60 um minimum-width rule.
    rectangle metal4 [expr {$x - 0.59}] [expr {$y - 0.59}] [expr {$x + 0.59}] [expr {$y + 0.59}]
    rectangle via4   [expr {$x - 0.59}] [expr {$y - 0.59}] [expr {$x + 0.59}] [expr {$y + 0.59}]
    rectangle metal5 [expr {$x - 0.80}] [expr {$y - 0.80}] [expr {$x + 0.80}] [expr {$y + 0.80}]
}

proc pin {name number layer x1 y1 x2 y2} {
    box values ${x1}um ${y1}um ${x2}um ${y2}um
    label $name center $layer
    port make $number
    port class bidirectional
    port use signal
}

load cdac_route_probe -silent
box values 0 0 0 0

# Four real 3 um x 3 um MIMs on a relaxed probe pitch.
foreach {name x y} {
    X00 0 0
    X01 12 0
    X10 0 8
    X11 12 8
} {
    getcell mim_unit child 0 0 parent ${x}um ${y}um
    identify $name
}

# All C2 terminals (local coordinate x=+2.17 um, y=0) are connected by
# actual M3 rectangles.  The horizontal bars intentionally merge into each
# MIM bottom-electrode M3; the left vertical bar joins the two rows.
rectangle metal3 -2.20 -0.30 14.30 0.30
rectangle metal3 -2.20 7.70 14.30 8.30
rectangle metal3 -2.20 -0.30 -1.60 8.30
rectangle metal3 -5.00 3.70 -1.60 4.30
pin TOP 1 metal3 -5.00 3.70 -4.40 4.30

# C1 terminal centers are at local x=-0.73 um.  Each unit gets a vertical
# M4 escape into the free channel above its row, then a horizontal M4 branch
# to a dedicated M5 trunk.  B0 uses X00 and X11; B1 uses X01 and X10.
set c1_l -0.73
set c1_r 11.27

# Row 0 branches, channel y=2.20 um.
rectangle metal4 [expr {$c1_l - 0.20}] -0.20 [expr {$c1_l + 0.20}] 2.40
rectangle metal4 -6.00 2.00 [expr {$c1_l + 0.20}] 2.40
via45 -6.00 2.20
rectangle metal4 [expr {$c1_r - 0.20}] -0.20 [expr {$c1_r + 0.20}] 2.40
rectangle metal4 [expr {$c1_r - 0.20}] 2.00 20.80 2.40
via45 20.80 2.20

# Row 1 branches, channel y=10.20 um.
rectangle metal4 [expr {$c1_l - 0.20}] 7.80 [expr {$c1_l + 0.20}] 10.40
rectangle metal4 -2.80 10.00 [expr {$c1_l + 0.20}] 10.40
via45 -2.80 10.20
rectangle metal4 [expr {$c1_r - 0.20}] 7.80 [expr {$c1_r + 0.20}] 10.40
rectangle metal4 [expr {$c1_r - 0.20}] 10.00 24.00 10.40
via45 24.00 10.20

# Four separate M5 trunks.  Each net's left/right trunks are joined by a
# genuine M4 peripheral bus at a distinct y, with via4 only where intended.
rectangle metal5 -6.80 1.40 -5.20 14.80
rectangle metal5 23.20 9.40 24.80 14.80
rectangle metal5 -3.60 9.40 -2.00 16.80
rectangle metal5 20.00 1.40 21.60 16.80

rectangle metal4 -6.00 13.80 24.00 14.20
via45 -6.00 14.00
via45 24.00 14.00
rectangle metal4 -2.80 15.80 20.80 16.20
via45 -2.80 16.00
via45 20.80 16.00

pin B0 2 metal5 23.20 13.00 24.80 14.80
pin B1 3 metal5 20.00 15.00 21.60 16.80

save cdac_route_probe
select top cell
expand
drc on
drc check
drc catchup
puts "PROBE_DRC_COUNT [drc list count total]"
puts "PROBE_DRC_DETAILS [drc listall why]"
gds write cdac_route_probe.gds

flatten cdac_route_probe_flat
load cdac_route_probe_flat
save cdac_route_probe_flat
extract all
ext2spice lvs
ext2spice -o cdac_route_probe_flat.lvs.spice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o cdac_route_probe_flat.pex.spice
quit -noprompt
