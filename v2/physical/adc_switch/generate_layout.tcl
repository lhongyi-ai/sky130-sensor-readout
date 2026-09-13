# A real SKY130 sampling transmission-gate cell. Run in a fresh output directory
# selected by TG_RUN_DIR. Geometry units below are explicit micrometres.
set out $::env(TG_RUN_DIR)
file mkdir $out
cd $out
drc off
snap internal
foreach {name kind width} {tg_nfet8 nfet 8 tg_pfet16 pfet 16} {
    load $name
    box values 0 0 0 0
    set defaults [sky130::sky130_fd_pr__${kind}_01v8_defaults]
    set params [dict merge $defaults [dict create w $width l 0.15 nf 1 guard 1]]
    sky130::sky130_fd_pr__${kind}_01v8_draw $params
    save $name
}

load adc_tgate_layout
box values 0 0 0 0
getcell tg_nfet8 child 0 0 parent 5um 10um
identify XN
getcell tg_pfet16 child 0 0 parent 10um 10um
identify XP

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

# Contact source/drain away from their narrow local M1 rails so via enclosures
# do not bridge the transistor gate or neighboring diffusion contact.
foreach cx {5 10} {
    rectangle metal1 [expr {$cx-.68}] 9.32 [expr {$cx-.105}] 9.68
    rectangle metal1 [expr {$cx+.105}] 10.32 [expr {$cx+.68}] 10.68
    via12 [expr {$cx-.5}] 9.5
    via12 [expr {$cx+.5}] 10.5
}
rectangle metal2 3 9.32 9.68 9.68
rectangle metal2 3 10.32 10.68 10.68
pin A 1 metal2 3 10.32 3.4 10.68
pin B 2 metal2 3 9.32 3.4 9.68

# PCell gate contacts include poly/LI/M1, but isolated M1 landing pads must be
# enlarged to meet the M1 minimum-area rule (including unused bottom landings).
foreach {cx y1 y2} {5 14.16 14.39 5 5.61 5.84 10 18.205 18.435 10 1.565 1.795} {
    rectangle metal1 [expr {$cx-.2}] $y1 [expr {$cx+.2}] $y2
}
pin EN 3 metal1 4.8 14.16 5.2 14.39
pin ENB 4 metal1 9.8 18.205 10.2 18.435

# Guard-ring body taps: add local-interconnect-to-M1 contacts and explicit pins.
foreach {cx cy name number} {10 1.17 VDD 5 5 5.215 VSS 6} {
    rectangle viali [expr {$cx-.085}] [expr {$cy-.085}] [expr {$cx+.085}] [expr {$cy+.085}]
    rectangle metal1 [expr {$cx-.145}] [expr {$cy-.145}] [expr {$cx+.145}] [expr {$cy+.145}]
    pin $name $number metal1 [expr {$cx-.145}] [expr {$cy-.145}] [expr {$cx+.145}] [expr {$cy+.145}]
    port use [expr {$name eq "VDD" ? "power" : "ground"}]
}
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
# Full RC is produced by extract_rc.tcl in a fresh Magic process.
quit -noprompt
