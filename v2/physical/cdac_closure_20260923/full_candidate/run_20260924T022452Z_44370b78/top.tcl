set out [file dirname [info script]]
cd $out
snap internal
drc off
proc rectangle {layer x1 y1 x2 y2} {box values ${x1}um ${y1}um ${x2}um ${y2}um; paint $layer}
proc via45 {x y} {rectangle metal4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle via4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle metal5 [expr {$x-0.80}] [expr {$y-0.80}] [expr {$x+0.80}] [expr {$y+0.80}]}
proc pin {name number layer x1 y1 x2 y2} {box values ${x1}um ${y1}um ${x2}um ${y2}um; label $name center $layer; port make $number; port class bidirectional; port use signal}
load c3gap_diff -silent
box values 0 0 0 0
getcell c3gap_p child 0 0 parent 44.8um 0um; identify X_P
rectangle metal3 52.770 5.800 53.170 6.200
pin P_TOP 1 metal3 52.770 5.800 53.170 6.200
rectangle metal4 264.600 431.800 265.000 432.200
pin P_B11 2 metal4 264.600 431.800 265.000 432.200
rectangle metal4 264.600 433.800 265.000 434.200
pin P_B10 3 metal4 264.600 433.800 265.000 434.200
rectangle metal4 264.600 435.800 265.000 436.200
pin P_B9 4 metal4 264.600 435.800 265.000 436.200
rectangle metal4 264.600 437.800 265.000 438.200
pin P_B8 5 metal4 264.600 437.800 265.000 438.200
rectangle metal4 264.600 439.800 265.000 440.200
pin P_B7 6 metal4 264.600 439.800 265.000 440.200
rectangle metal4 264.600 441.800 265.000 442.200
pin P_B6 7 metal4 264.600 441.800 265.000 442.200
rectangle metal4 264.600 443.800 265.000 444.200
pin P_B5 8 metal4 264.600 443.800 265.000 444.200
rectangle metal4 264.600 445.800 265.000 446.200
pin P_B4 9 metal4 264.600 445.800 265.000 446.200
rectangle metal4 264.600 447.800 265.000 448.200
pin P_B3 10 metal4 264.600 447.800 265.000 448.200
rectangle metal4 264.600 449.800 265.000 450.200
pin P_B2 11 metal4 264.600 449.800 265.000 450.200
rectangle metal4 264.600 451.800 265.000 452.200
pin P_B1 12 metal4 264.600 451.800 265.000 452.200
rectangle metal4 264.600 453.800 265.000 454.200
pin P_B0 13 metal4 264.600 453.800 265.000 454.200
rectangle metal4 264.600 455.800 265.000 456.200
pin P_DUMMY 14 metal4 264.600 455.800 265.000 456.200
rectangle metal3 46.770 -0.200 47.170 0.200
pin P_EDGE_BIAS 15 metal3 46.770 -0.200 47.170 0.200
getcell c3gap_n child 0 0 parent 530.4um 0um; identify X_N
rectangle metal3 538.370 5.800 538.770 6.200
pin N_TOP 16 metal3 538.370 5.800 538.770 6.200
rectangle metal4 750.200 431.800 750.600 432.200
pin N_B11 17 metal4 750.200 431.800 750.600 432.200
rectangle metal4 750.200 433.800 750.600 434.200
pin N_B10 18 metal4 750.200 433.800 750.600 434.200
rectangle metal4 750.200 435.800 750.600 436.200
pin N_B9 19 metal4 750.200 435.800 750.600 436.200
rectangle metal4 750.200 437.800 750.600 438.200
pin N_B8 20 metal4 750.200 437.800 750.600 438.200
rectangle metal4 750.200 439.800 750.600 440.200
pin N_B7 21 metal4 750.200 439.800 750.600 440.200
rectangle metal4 750.200 441.800 750.600 442.200
pin N_B6 22 metal4 750.200 441.800 750.600 442.200
rectangle metal4 750.200 443.800 750.600 444.200
pin N_B5 23 metal4 750.200 443.800 750.600 444.200
rectangle metal4 750.200 445.800 750.600 446.200
pin N_B4 24 metal4 750.200 445.800 750.600 446.200
rectangle metal4 750.200 447.800 750.600 448.200
pin N_B3 25 metal4 750.200 447.800 750.600 448.200
rectangle metal4 750.200 449.800 750.600 450.200
pin N_B2 26 metal4 750.200 449.800 750.600 450.200
rectangle metal4 750.200 451.800 750.600 452.200
pin N_B1 27 metal4 750.200 451.800 750.600 452.200
rectangle metal4 750.200 453.800 750.600 454.200
pin N_B0 28 metal4 750.200 453.800 750.600 454.200
rectangle metal4 750.200 455.800 750.600 456.200
pin N_DUMMY 29 metal4 750.200 455.800 750.600 456.200
rectangle metal3 532.370 -0.200 532.770 0.200
pin N_EDGE_BIAS 30 metal3 532.370 -0.200 532.770 0.200
save c3gap_diff
select top cell
expand
drc on
drc style drc(full)
drc check
drc catchup
puts "CANDIDATE_DRC_COUNT TOP [drc list count total]"
puts "CANDIDATE_DRC_DETAILS TOP [drc listall why]"
gds write c3gap_diff.gds
drc off
flatten c3gap_diff_flat
load c3gap_diff_flat
save c3gap_diff_flat
extract all
ext2spice lvs
ext2spice -o c3gap_diff.lvs.spice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o c3gap_diff.cap.spice
quit -noprompt
