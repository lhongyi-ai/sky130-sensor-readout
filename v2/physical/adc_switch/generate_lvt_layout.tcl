# Generate an independently named two-low-Vt-device sampling switch candidate.
# Resolve contacts from generated PCell labels; do not guess LVT contact offsets.
set out $::env(TG_RUN_DIR)
file mkdir $out
cd $out
drc off
snap internal
set wn $::env(TG_CAND_WN)
set wp $::env(TG_CAND_WP)
foreach {name kind width length} [list tg_nfet_lvt nfet $wn .15 tg_pfet_lvt pfet $wp .35] {
    load $name
    box values 0 0 0 0
    set defaults [sky130::sky130_fd_pr__${kind}_01v8_lvt_defaults]
    set params [dict merge $defaults [dict create w $width l $length nf 1 guard 1]]
    sky130::sky130_fd_pr__${kind}_01v8_lvt_draw $params
    save $name
}
proc contact {cell port ox oy} {
    set stream [open "${cell}.mag" r]
    set contents [read $stream]
    close $stream
    if {![regexp -line {^magscale 1 2$} $contents]} {error "Review PCell coordinate scale"}
    foreach line [split $contents \n] {
        if {[string match "rlabel * $port" $line]} {
            set x [expr {[lindex $line 2]*.005+$ox}]
            set y [expr {[lindex $line 3]*.005+$oy}]
            return [list $x $y]
        }
    }
    error "No contact $port in $cell"
}
proc rectangle {layer x1 y1 x2 y2} {
    box values ${x1}um ${y1}um ${x2}um ${y2}um
    paint $layer
}
proc pin {name number layer x1 y1 x2 y2} {
    box values ${x1}um ${y1}um ${x2}um ${y2}um
    label $name center $layer
    port make $number
    port class bidirectional
    port use signal
}
proc via12 {x y} {
    rectangle metal1 [expr {$x-.18}] [expr {$y-.18}] [expr {$x+.18}] [expr {$y+.18}]
    rectangle via1 [expr {$x-.13}] [expr {$y-.13}] [expr {$x+.13}] [expr {$y+.13}]
    rectangle metal2 [expr {$x-.18}] [expr {$y-.18}] [expr {$x+.18}] [expr {$y+.18}]
}
load adc_tgate_layout
box values 0 0 0 0
getcell tg_nfet_lvt child 0 0 parent 4um 6um
identify XN
getcell tg_pfet_lvt child 0 0 parent 9um 6um
identify XP
set dmax 0
set smax 0
foreach {cell ox name number supply snumber} {tg_nfet_lvt 4 EN 3 VSS 6 tg_pfet_lvt 9 ENB 4 VDD 5} {
    lassign [contact $cell D $ox 6] dx dy
    lassign [contact $cell S $ox 6] sx sy
    set vd [expr {$dx-.35}]
    set vs [expr {$sx+.35}]
    rectangle metal1 [expr {$vd-.18}] 5.32 [expr {$dx+.10}] 5.68
    rectangle metal1 [expr {$sx-.10}] 6.32 [expr {$vs+.18}] 6.68
    via12 $vd 5.5
    via12 $vs 6.5
    set dmax [expr {max($dmax,$vd+.18)}]
    set smax [expr {max($smax,$vs+.18)}]
    lassign [contact $cell G $ox 6] gx gy
    # Both top and unused bottom M1 gate landings require minimum area.
    foreach y [list $gy [expr {12-$gy}]] {
        rectangle metal1 [expr {$gx-.2}] [expr {$y-.115}] [expr {$gx+.2}] [expr {$y+.115}]
    }
    pin $name $number metal1 [expr {$gx-.2}] [expr {$gy-.115}] [expr {$gx+.2}] [expr {$gy+.115}]
    lassign [contact $cell B $ox 6] bx by
    rectangle viali [expr {$bx-.085}] [expr {$by-.085}] [expr {$bx+.085}] [expr {$by+.085}]
    rectangle metal1 [expr {$bx-.145}] [expr {$by-.145}] [expr {$bx+.145}] [expr {$by+.145}]
    pin $supply $snumber metal1 [expr {$bx-.145}] [expr {$by-.145}] [expr {$bx+.145}] [expr {$by+.145}]
    port use [expr {$supply eq "VDD" ? "power" : "ground"}]
}
rectangle metal2 2 5.32 $dmax 5.68
rectangle metal2 2 6.32 $smax 6.68
pin A 1 metal2 2 6.32 2.4 6.68
pin B 2 metal2 2 5.32 2.4 5.68
save adc_tgate_layout
select top cell
expand
drc on
drc check
drc catchup
puts "TG_DRC_COUNT [drc list count total]"
puts "TG_DRC_DETAILS [drc listall why]"
gds write adc_tgate_layout.gds
extract all
ext2spice lvs
ext2spice -o adc_tgate_layout.lvs.spice
flatten adc_tgate_flat
load adc_tgate_flat
save adc_tgate_flat
extract all
ext2spice lvs
ext2spice -o adc_tgate_flat.lvs.spice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o adc_tgate_flat.cap.spice
quit -noprompt
