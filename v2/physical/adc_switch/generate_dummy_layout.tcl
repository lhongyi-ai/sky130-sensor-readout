# Four-device dedicated sampling switch. Dummy D=S connects only to held B.
set out $::env(TG_RUN_DIR)
file mkdir $out
cd $out
drc off
snap internal
set wn $::env(TG_CAND_WN)
set wp $::env(TG_CAND_WP)
foreach {name kind width length} [list tg_nfet_lvt nfet $wn .15 tg_pfet_lvt pfet $wp .35 tg_nfet_dummy nfet [expr {$wn/2}] .15 tg_pfet_dummy pfet [expr {$wp/2}] .35] {
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
    if {![regexp -line {^magscale 1 2$} $contents]} {error "Review PCell scale"}
    foreach line [split $contents \n] {
        if {[string match "rlabel * $port" $line]} {
            return [list [expr {[lindex $line 2]*.005+$ox}] [expr {[lindex $line 3]*.005+$oy}]]
        }
    }
    error "Missing contact $port in $cell"
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
proc via23 {x y} {
    rectangle metal2 [expr {$x-.25}] [expr {$y-.25}] [expr {$x+.25}] [expr {$y+.25}]
    rectangle via2 [expr {$x-.16}] [expr {$y-.16}] [expr {$x+.16}] [expr {$y+.16}]
    rectangle metal3 [expr {$x-.25}] [expr {$y-.25}] [expr {$x+.25}] [expr {$y+.25}]
}
load adc_tgate_layout
foreach {cell ox oy id} {tg_nfet_lvt 4 12 XN tg_pfet_lvt 9 12 XP tg_nfet_dummy 4 3 XND tg_pfet_dummy 9 3 XPD} {
    box values 0 0 0 0
    getcell $cell child 0 0 parent ${ox}um ${oy}um
    identify $id
}
# Both PMOS bodies use VDD: merge their close n-well regions rather than leave
# a sub-minimum gap between two same-potential wells.
rectangle nwell 7.845 6 10.155 8
set dmax 0
set smax 0
set dummymax 0
foreach {cell ox oy dummy clock supply} {tg_nfet_lvt 4 12 0 EN VSS tg_pfet_lvt 9 12 0 ENB VDD tg_nfet_dummy 4 3 1 ENB VSS tg_pfet_dummy 9 3 1 EN VDD} {
    lassign [contact $cell D $ox $oy] dx dy
    lassign [contact $cell S $ox $oy] sx sy
    if {!$dummy} {
        set vd [expr {$dx-.35}]
        set vs [expr {$sx+.35}]
        rectangle metal1 [expr {$vd-.18}] 11.32 [expr {$dx+.10}] 11.68
        rectangle metal1 [expr {$sx-.10}] 12.32 [expr {$vs+.18}] 12.68
        via12 $vd 11.5
        via12 $vs 12.5
        set dmax [expr {max($dmax,$vd+.18)}]
        set smax [expr {max($smax,$vs+.18)}]
    } else {
        # Both diffusions are shorted in M1 above the insulated poly channel.
        rectangle metal1 [expr {$dx-.10}] 2.82 [expr {$sx+.55}] 3.18
        via12 [expr {$sx+.35}] 3
        set dummymax [expr {max($dummymax,$sx+.53)}]
    }
    lassign [contact $cell G $ox $oy] gx gy
    foreach y [list $gy [expr {2*$oy-$gy}]] {
        rectangle metal1 [expr {$gx-.2}] [expr {$y-.115}] [expr {$gx+.2}] [expr {$y+.115}]
    }
    # Lift clock vias above the small gate landing to preserve D/S spacing.
    set yy [expr {$gy+.55}]
    rectangle metal1 [expr {$gx-.14}] [expr {$gy-.10}] [expr {$gx+.14}] $yy
    via12 $gx $yy
    set bus [expr {$clock eq "EN" ? 13 : 14.5}]
    rectangle metal2 [expr {$gx-.18}] [expr {$yy-.18}] [expr {$bus+.25}] [expr {$yy+.18}]
    via23 $bus $yy
    lassign [contact $cell B $ox $oy] bx by
    rectangle viali [expr {$bx-.085}] [expr {$by-.085}] [expr {$bx+.085}] [expr {$by+.085}]
    set pbus [expr {$supply eq "VSS" ? .5 : 16}]
    rectangle metal1 [expr {min($bx,$pbus)-.145}] [expr {$by-.145}] [expr {max($bx,$pbus)+.145}] [expr {$by+.145}]
    via12 $pbus $by
    via23 $pbus $by
}
rectangle metal2 2 11.32 $dmax 11.68
rectangle metal2 2 12.32 $smax 12.68
rectangle metal2 2.72 2.82 3.08 11.68
rectangle metal2 2.72 2.82 $dummymax 3.18
pin A 1 metal2 2 12.32 2.4 12.68
pin B 2 metal2 2 11.32 2.4 11.68
rectangle metal3 12.8 4.5 13.2 17.2
rectangle metal3 14.3 4.5 14.7 17.2
pin EN 3 metal3 12.8 16.8 13.2 17.2
pin ENB 4 metal3 14.3 16.8 14.7 17.2
rectangle metal3 .3 0 .7 10
rectangle metal3 15.8 0 16.2 10
pin VDD 5 metal3 15.8 0 16.2 .4
port use power
pin VSS 6 metal3 .3 0 .7 .4
port use ground
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
