# Our generated PDK primitive smoke cells, not a sensor-core layout.
# Run with the installed sky130A.magicrc, PDK_ROOT=/foss/pdks.
set out $::env(SKY130_PRIMITIVE_OUT)
file mkdir $out
cd $out
random seed 1302026
foreach kind {mim_unit nfet_unit} {
    load $kind -silent
    box values 0 0 0 0
    if {$kind == "mim_unit"} {
        set params [dict merge [sky130::sky130_fd_pr__cap_mim_m3_1_defaults] {w 3.0 l 3.0 stack 0 doports 1}]
        sky130::sky130_fd_pr__cap_mim_m3_1_draw $params
    } else {
        set params [dict merge [sky130::sky130_fd_pr__nfet_01v8_defaults] {w 2.0 l 1.0 guard 1 doports 1}]
        sky130::sky130_fd_pr__nfet_01v8_draw $params
    }
    save $kind
    select top cell
    puts "CELL_BBOX $kind [box values]"
    drc check
    drc catchup
    puts "DRC_COUNT $kind [drc list count total]"
    puts "DRC_DETAILS $kind [drc listall why]"
    extract all
    ext2spice lvs
    ext2spice -o ${kind}_lvs.spice
    ext2spice cthresh 0
    ext2spice rthresh 0
    ext2spice -o ${kind}_pex.spice
    gds write ${kind}.gds
}
quit -noprompt
