set out [file dirname [info script]]
cd $out
snap internal
drc off
proc rectangle {layer x1 y1 x2 y2} {box values ${x1}um ${y1}um ${x2}um ${y2}um; paint $layer}
proc via45 {x y} {rectangle metal4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle via4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle metal5 [expr {$x-0.80}] [expr {$y-0.80}] [expr {$x+0.80}] [expr {$y+0.80}]}
proc pin {name number layer x y} {box values [expr {$x-0.1}]um [expr {$y-0.1}]um [expr {$x+0.1}]um [expr {$y+0.1}]um; label $name center $layer; port make $number; port class bidirectional; port use signal}
load p1cdac3_m5_inside -silent
box values 0 0 0 0
getcell mim_unit child 0 0 parent 6um 6um; identify X_r01_c01
rectangle metal4 5.070 5.800 5.470 9.200
getcell mim_unit child 0 0 parent 12um 6um; identify X_r01_c02
rectangle metal4 11.070 5.800 11.470 9.200
getcell mim_unit child 0 0 parent 18um 6um; identify X_r01_c03
rectangle metal4 17.070 5.800 17.470 9.200
getcell mim_unit child 0 0 parent 24um 6um; identify X_r01_c04
rectangle metal4 23.070 5.800 23.470 9.200
rectangle metal3 3.570 4.300 26.430 7.700
rectangle metal4 -4.000 8.800 23.470 9.200
via45 -4 9
getcell mim_unit child 0 0 parent 6um 12um; identify X_r02_c01
rectangle metal4 5.070 11.800 5.470 15.200
getcell mim_unit child 0 0 parent 12um 12um; identify X_r02_c02
rectangle metal4 11.070 11.800 11.470 15.200
getcell mim_unit child 0 0 parent 18um 12um; identify X_r02_c03
rectangle metal4 17.070 11.800 17.470 15.200
getcell mim_unit child 0 0 parent 24um 12um; identify X_r02_c04
rectangle metal4 23.070 11.800 23.470 15.200
rectangle metal3 3.570 10.300 26.430 13.700
rectangle metal4 -4.000 14.800 23.470 15.200
via45 -4 15
getcell mim_unit child 0 0 parent 6um 18um; identify X_r03_c01
rectangle metal4 5.070 17.800 5.470 21.200
getcell mim_unit child 0 0 parent 12um 18um; identify X_r03_c02
rectangle metal4 11.070 17.800 11.470 21.200
getcell mim_unit child 0 0 parent 18um 18um; identify X_r03_c03
rectangle metal4 17.070 17.800 17.470 21.200
getcell mim_unit child 0 0 parent 24um 18um; identify X_r03_c04
rectangle metal4 23.070 17.800 23.470 21.200
rectangle metal3 3.570 16.300 26.430 19.700
rectangle metal4 -4.000 20.800 23.470 21.200
via45 -4 21
getcell mim_unit child 0 0 parent 6um 24um; identify X_r04_c01
rectangle metal4 5.070 23.800 5.470 27.200
getcell mim_unit child 0 0 parent 12um 24um; identify X_r04_c02
rectangle metal4 11.070 23.800 11.470 27.200
getcell mim_unit child 0 0 parent 18um 24um; identify X_r04_c03
rectangle metal4 17.070 23.800 17.470 27.200
getcell mim_unit child 0 0 parent 24um 24um; identify X_r04_c04
rectangle metal4 23.070 23.800 23.470 27.200
rectangle metal3 3.570 22.300 26.430 25.700
rectangle metal4 -4.000 26.800 23.470 27.200
via45 -4 27
getcell mim_unit child 0 0 parent 6um 30um; identify X_r05_c01
rectangle metal4 5.070 29.800 5.470 33.200
getcell mim_unit child 0 0 parent 12um 30um; identify X_r05_c02
rectangle metal4 11.070 29.800 11.470 33.200
getcell mim_unit child 0 0 parent 18um 30um; identify X_r05_c03
rectangle metal4 17.070 29.800 17.470 33.200
getcell mim_unit child 0 0 parent 24um 30um; identify X_r05_c04
rectangle metal4 23.070 29.800 23.470 33.200
rectangle metal3 3.570 28.300 26.430 31.700
rectangle metal4 -4.000 32.800 23.470 33.200
via45 -4 33
getcell mim_unit child 0 0 parent 6um 36um; identify X_r06_c01
rectangle metal4 5.070 35.800 5.470 39.200
getcell mim_unit child 0 0 parent 12um 36um; identify X_r06_c02
rectangle metal4 11.070 35.800 11.470 39.200
getcell mim_unit child 0 0 parent 18um 36um; identify X_r06_c03
rectangle metal4 17.070 35.800 17.470 39.200
getcell mim_unit child 0 0 parent 24um 36um; identify X_r06_c04
rectangle metal4 23.070 35.800 23.470 39.200
rectangle metal3 3.570 34.300 26.430 37.700
rectangle metal4 -4.000 38.800 23.470 39.200
via45 -4 39
getcell mim_unit child 0 0 parent 6um 42um; identify X_r07_c01
rectangle metal4 5.070 41.800 5.470 45.200
getcell mim_unit child 0 0 parent 12um 42um; identify X_r07_c02
rectangle metal4 11.070 41.800 11.470 45.200
getcell mim_unit child 0 0 parent 18um 42um; identify X_r07_c03
rectangle metal4 17.070 41.800 17.470 45.200
getcell mim_unit child 0 0 parent 24um 42um; identify X_r07_c04
rectangle metal4 23.070 41.800 23.470 45.200
rectangle metal3 3.570 40.300 26.430 43.700
rectangle metal4 -4.000 44.800 23.470 45.200
via45 -4 45
getcell mim_unit child 0 0 parent 6um 48um; identify X_r08_c01
rectangle metal4 5.070 47.800 5.470 51.200
getcell mim_unit child 0 0 parent 12um 48um; identify X_r08_c02
rectangle metal4 11.070 47.800 11.470 51.200
getcell mim_unit child 0 0 parent 18um 48um; identify X_r08_c03
rectangle metal4 17.070 47.800 17.470 51.200
getcell mim_unit child 0 0 parent 24um 48um; identify X_r08_c04
rectangle metal4 23.070 47.800 23.470 51.200
rectangle metal3 3.570 46.300 26.430 49.700
rectangle metal4 -4.000 50.800 23.470 51.200
via45 -4 51
getcell mim_unit child 0 0 parent 6um 54um; identify X_r09_c01
rectangle metal4 5.070 53.800 5.470 57.200
getcell mim_unit child 0 0 parent 12um 54um; identify X_r09_c02
rectangle metal4 11.070 53.800 11.470 57.200
getcell mim_unit child 0 0 parent 18um 54um; identify X_r09_c03
rectangle metal4 17.070 53.800 17.470 57.200
getcell mim_unit child 0 0 parent 24um 54um; identify X_r09_c04
rectangle metal4 23.070 53.800 23.470 57.200
rectangle metal3 3.570 52.300 26.430 55.700
rectangle metal4 -4.000 56.800 23.470 57.200
via45 -4 57
getcell mim_unit child 0 0 parent 6um 60um; identify X_r10_c01
rectangle metal4 5.070 59.800 5.470 63.200
getcell mim_unit child 0 0 parent 12um 60um; identify X_r10_c02
rectangle metal4 11.070 59.800 11.470 63.200
getcell mim_unit child 0 0 parent 18um 60um; identify X_r10_c03
rectangle metal4 17.070 59.800 17.470 63.200
getcell mim_unit child 0 0 parent 24um 60um; identify X_r10_c04
rectangle metal4 23.070 59.800 23.470 63.200
rectangle metal3 3.570 58.300 26.430 61.700
rectangle metal4 -4.000 62.800 23.470 63.200
via45 -4 63
getcell mim_unit child 0 0 parent 6um 66um; identify X_r11_c01
rectangle metal4 5.070 65.800 5.470 69.200
getcell mim_unit child 0 0 parent 12um 66um; identify X_r11_c02
rectangle metal4 11.070 65.800 11.470 69.200
getcell mim_unit child 0 0 parent 18um 66um; identify X_r11_c03
rectangle metal4 17.070 65.800 17.470 69.200
getcell mim_unit child 0 0 parent 24um 66um; identify X_r11_c04
rectangle metal4 23.070 65.800 23.470 69.200
rectangle metal3 3.570 64.300 26.430 67.700
rectangle metal4 -4.000 68.800 23.470 69.200
via45 -4 69
getcell mim_unit child 0 0 parent 6um 72um; identify X_r12_c01
rectangle metal4 5.070 71.800 5.470 75.200
getcell mim_unit child 0 0 parent 12um 72um; identify X_r12_c02
rectangle metal4 11.070 71.800 11.470 75.200
getcell mim_unit child 0 0 parent 18um 72um; identify X_r12_c03
rectangle metal4 17.070 71.800 17.470 75.200
getcell mim_unit child 0 0 parent 24um 72um; identify X_r12_c04
rectangle metal4 23.070 71.800 23.470 75.200
rectangle metal3 3.570 70.300 26.430 73.700
rectangle metal4 -4.000 74.800 23.470 75.200
via45 -4 75
getcell mim_unit child 0 0 parent 6um 78um; identify X_r13_c01
rectangle metal4 5.070 77.800 5.470 81.200
getcell mim_unit child 0 0 parent 12um 78um; identify X_r13_c02
rectangle metal4 11.070 77.800 11.470 81.200
getcell mim_unit child 0 0 parent 18um 78um; identify X_r13_c03
rectangle metal4 17.070 77.800 17.470 81.200
getcell mim_unit child 0 0 parent 24um 78um; identify X_r13_c04
rectangle metal4 23.070 77.800 23.470 81.200
rectangle metal3 3.570 76.300 26.430 79.700
rectangle metal4 -4.000 80.800 23.470 81.200
via45 -4 81
getcell mim_unit child 0 0 parent 6um 84um; identify X_r14_c01
rectangle metal4 5.070 83.800 5.470 87.200
getcell mim_unit child 0 0 parent 12um 84um; identify X_r14_c02
rectangle metal4 11.070 83.800 11.470 87.200
getcell mim_unit child 0 0 parent 18um 84um; identify X_r14_c03
rectangle metal4 17.070 83.800 17.470 87.200
getcell mim_unit child 0 0 parent 24um 84um; identify X_r14_c04
rectangle metal4 23.070 83.800 23.470 87.200
rectangle metal3 3.570 82.300 26.430 85.700
rectangle metal4 -4.000 86.800 23.470 87.200
via45 -4 87
getcell mim_unit child 0 0 parent 6um 90um; identify X_r15_c01
rectangle metal4 5.070 89.800 5.470 93.200
getcell mim_unit child 0 0 parent 12um 90um; identify X_r15_c02
rectangle metal4 11.070 89.800 11.470 93.200
getcell mim_unit child 0 0 parent 18um 90um; identify X_r15_c03
rectangle metal4 17.070 89.800 17.470 93.200
getcell mim_unit child 0 0 parent 24um 90um; identify X_r15_c04
rectangle metal4 23.070 89.800 23.470 93.200
rectangle metal3 3.570 88.300 26.430 91.700
rectangle metal4 -4.000 92.800 23.470 93.200
via45 -4 93
getcell mim_unit child 0 0 parent 6um 96um; identify X_r16_c01
rectangle metal4 5.070 95.800 5.470 99.200
getcell mim_unit child 0 0 parent 12um 96um; identify X_r16_c02
rectangle metal4 11.070 95.800 11.470 99.200
getcell mim_unit child 0 0 parent 18um 96um; identify X_r16_c03
rectangle metal4 17.070 95.800 17.470 99.200
getcell mim_unit child 0 0 parent 24um 96um; identify X_r16_c04
rectangle metal4 23.070 95.800 23.470 99.200
rectangle metal3 3.570 94.300 26.430 97.700
rectangle metal4 -4.000 98.800 23.470 99.200
via45 -4 99
getcell mim_unit child 0 0 parent 6um 102um; identify X_r17_c01
rectangle metal4 5.070 101.800 5.470 105.200
getcell mim_unit child 0 0 parent 12um 102um; identify X_r17_c02
rectangle metal4 11.070 101.800 11.470 105.200
getcell mim_unit child 0 0 parent 18um 102um; identify X_r17_c03
rectangle metal4 17.070 101.800 17.470 105.200
getcell mim_unit child 0 0 parent 24um 102um; identify X_r17_c04
rectangle metal4 23.070 101.800 23.470 105.200
rectangle metal3 3.570 100.300 26.430 103.700
rectangle metal4 -4.000 104.800 23.470 105.200
via45 -4 105
getcell mim_unit child 0 0 parent 6um 108um; identify X_r18_c01
rectangle metal4 5.070 107.800 5.470 111.200
getcell mim_unit child 0 0 parent 12um 108um; identify X_r18_c02
rectangle metal4 11.070 107.800 11.470 111.200
getcell mim_unit child 0 0 parent 18um 108um; identify X_r18_c03
rectangle metal4 17.070 107.800 17.470 111.200
getcell mim_unit child 0 0 parent 24um 108um; identify X_r18_c04
rectangle metal4 23.070 107.800 23.470 111.200
rectangle metal3 3.570 106.300 26.430 109.700
rectangle metal4 -4.000 110.800 23.470 111.200
via45 -4 111
getcell mim_unit child 0 0 parent 6um 114um; identify X_r19_c01
rectangle metal4 5.070 113.800 5.470 117.200
getcell mim_unit child 0 0 parent 12um 114um; identify X_r19_c02
rectangle metal4 11.070 113.800 11.470 117.200
getcell mim_unit child 0 0 parent 18um 114um; identify X_r19_c03
rectangle metal4 17.070 113.800 17.470 117.200
getcell mim_unit child 0 0 parent 24um 114um; identify X_r19_c04
rectangle metal4 23.070 113.800 23.470 117.200
rectangle metal3 3.570 112.300 26.430 115.700
rectangle metal4 -4.000 116.800 23.470 117.200
via45 -4 117
getcell mim_unit child 0 0 parent 6um 120um; identify X_r20_c01
rectangle metal4 5.070 119.800 5.470 123.200
getcell mim_unit child 0 0 parent 12um 120um; identify X_r20_c02
rectangle metal4 11.070 119.800 11.470 123.200
getcell mim_unit child 0 0 parent 18um 120um; identify X_r20_c03
rectangle metal4 17.070 119.800 17.470 123.200
getcell mim_unit child 0 0 parent 24um 120um; identify X_r20_c04
rectangle metal4 23.070 119.800 23.470 123.200
rectangle metal3 3.570 118.300 26.430 121.700
rectangle metal4 -4.000 122.800 23.470 123.200
via45 -4 123
getcell mim_unit child 0 0 parent 6um 126um; identify X_r21_c01
rectangle metal4 5.070 125.800 5.470 129.200
getcell mim_unit child 0 0 parent 12um 126um; identify X_r21_c02
rectangle metal4 11.070 125.800 11.470 129.200
getcell mim_unit child 0 0 parent 18um 126um; identify X_r21_c03
rectangle metal4 17.070 125.800 17.470 129.200
getcell mim_unit child 0 0 parent 24um 126um; identify X_r21_c04
rectangle metal4 23.070 125.800 23.470 129.200
rectangle metal3 3.570 124.300 26.430 127.700
rectangle metal4 -4.000 128.800 23.470 129.200
via45 -4 129
getcell mim_unit child 0 0 parent 6um 132um; identify X_r22_c01
rectangle metal4 5.070 131.800 5.470 135.200
getcell mim_unit child 0 0 parent 12um 132um; identify X_r22_c02
rectangle metal4 11.070 131.800 11.470 135.200
getcell mim_unit child 0 0 parent 18um 132um; identify X_r22_c03
rectangle metal4 17.070 131.800 17.470 135.200
getcell mim_unit child 0 0 parent 24um 132um; identify X_r22_c04
rectangle metal4 23.070 131.800 23.470 135.200
rectangle metal3 3.570 130.300 26.430 133.700
rectangle metal4 -4.000 134.800 23.470 135.200
via45 -4 135
getcell mim_unit child 0 0 parent 6um 138um; identify X_r23_c01
rectangle metal4 5.070 137.800 5.470 141.200
getcell mim_unit child 0 0 parent 12um 138um; identify X_r23_c02
rectangle metal4 11.070 137.800 11.470 141.200
getcell mim_unit child 0 0 parent 18um 138um; identify X_r23_c03
rectangle metal4 17.070 137.800 17.470 141.200
getcell mim_unit child 0 0 parent 24um 138um; identify X_r23_c04
rectangle metal4 23.070 137.800 23.470 141.200
rectangle metal3 3.570 136.300 26.430 139.700
rectangle metal4 -4.000 140.800 23.470 141.200
via45 -4 141
getcell mim_unit child 0 0 parent 6um 144um; identify X_r24_c01
rectangle metal4 5.070 143.800 5.470 147.200
getcell mim_unit child 0 0 parent 12um 144um; identify X_r24_c02
rectangle metal4 11.070 143.800 11.470 147.200
getcell mim_unit child 0 0 parent 18um 144um; identify X_r24_c03
rectangle metal4 17.070 143.800 17.470 147.200
getcell mim_unit child 0 0 parent 24um 144um; identify X_r24_c04
rectangle metal4 23.070 143.800 23.470 147.200
rectangle metal3 3.570 142.300 26.430 145.700
rectangle metal4 -4.000 146.800 23.470 147.200
via45 -4 147
getcell mim_unit child 0 0 parent 6um 150um; identify X_r25_c01
rectangle metal4 5.070 149.800 5.470 153.200
getcell mim_unit child 0 0 parent 12um 150um; identify X_r25_c02
rectangle metal4 11.070 149.800 11.470 153.200
getcell mim_unit child 0 0 parent 18um 150um; identify X_r25_c03
rectangle metal4 17.070 149.800 17.470 153.200
getcell mim_unit child 0 0 parent 24um 150um; identify X_r25_c04
rectangle metal4 23.070 149.800 23.470 153.200
rectangle metal3 3.570 148.300 26.430 151.700
rectangle metal4 -4.000 152.800 23.470 153.200
via45 -4 153
getcell mim_unit child 0 0 parent 6um 156um; identify X_r26_c01
rectangle metal4 5.070 155.800 5.470 159.200
getcell mim_unit child 0 0 parent 12um 156um; identify X_r26_c02
rectangle metal4 11.070 155.800 11.470 159.200
getcell mim_unit child 0 0 parent 18um 156um; identify X_r26_c03
rectangle metal4 17.070 155.800 17.470 159.200
getcell mim_unit child 0 0 parent 24um 156um; identify X_r26_c04
rectangle metal4 23.070 155.800 23.470 159.200
rectangle metal3 3.570 154.300 26.430 157.700
rectangle metal4 -4.000 158.800 23.470 159.200
via45 -4 159
getcell mim_unit child 0 0 parent 6um 162um; identify X_r27_c01
rectangle metal4 5.070 161.800 5.470 165.200
getcell mim_unit child 0 0 parent 12um 162um; identify X_r27_c02
rectangle metal4 11.070 161.800 11.470 165.200
getcell mim_unit child 0 0 parent 18um 162um; identify X_r27_c03
rectangle metal4 17.070 161.800 17.470 165.200
getcell mim_unit child 0 0 parent 24um 162um; identify X_r27_c04
rectangle metal4 23.070 161.800 23.470 165.200
rectangle metal3 3.570 160.300 26.430 163.700
rectangle metal4 -4.000 164.800 23.470 165.200
via45 -4 165
getcell mim_unit child 0 0 parent 6um 168um; identify X_r28_c01
rectangle metal4 5.070 167.800 5.470 171.200
getcell mim_unit child 0 0 parent 12um 168um; identify X_r28_c02
rectangle metal4 11.070 167.800 11.470 171.200
getcell mim_unit child 0 0 parent 18um 168um; identify X_r28_c03
rectangle metal4 17.070 167.800 17.470 171.200
getcell mim_unit child 0 0 parent 24um 168um; identify X_r28_c04
rectangle metal4 23.070 167.800 23.470 171.200
rectangle metal3 3.570 166.300 26.430 169.700
rectangle metal4 -4.000 170.800 23.470 171.200
via45 -4 171
getcell mim_unit child 0 0 parent 6um 174um; identify X_r29_c01
rectangle metal4 5.070 173.800 5.470 177.200
getcell mim_unit child 0 0 parent 12um 174um; identify X_r29_c02
rectangle metal4 11.070 173.800 11.470 177.200
getcell mim_unit child 0 0 parent 18um 174um; identify X_r29_c03
rectangle metal4 17.070 173.800 17.470 177.200
getcell mim_unit child 0 0 parent 24um 174um; identify X_r29_c04
rectangle metal4 23.070 173.800 23.470 177.200
rectangle metal3 3.570 172.300 26.430 175.700
rectangle metal4 -4.000 176.800 23.470 177.200
via45 -4 177
getcell mim_unit child 0 0 parent 6um 180um; identify X_r30_c01
rectangle metal4 5.070 179.800 5.470 183.200
getcell mim_unit child 0 0 parent 12um 180um; identify X_r30_c02
rectangle metal4 11.070 179.800 11.470 183.200
getcell mim_unit child 0 0 parent 18um 180um; identify X_r30_c03
rectangle metal4 17.070 179.800 17.470 183.200
getcell mim_unit child 0 0 parent 24um 180um; identify X_r30_c04
rectangle metal4 23.070 179.800 23.470 183.200
rectangle metal3 3.570 178.300 26.430 181.700
rectangle metal4 -4.000 182.800 23.470 183.200
via45 -4 183
getcell mim_unit child 0 0 parent 6um 186um; identify X_r31_c01
rectangle metal4 5.070 185.800 5.470 189.200
getcell mim_unit child 0 0 parent 12um 186um; identify X_r31_c02
rectangle metal4 11.070 185.800 11.470 189.200
getcell mim_unit child 0 0 parent 18um 186um; identify X_r31_c03
rectangle metal4 17.070 185.800 17.470 189.200
getcell mim_unit child 0 0 parent 24um 186um; identify X_r31_c04
rectangle metal4 23.070 185.800 23.470 189.200
rectangle metal3 3.570 184.300 26.430 187.700
rectangle metal4 -4.000 188.800 23.470 189.200
via45 -4 189
getcell mim_unit child 0 0 parent 6um 192um; identify X_r32_c01
rectangle metal4 5.070 191.800 5.470 195.200
getcell mim_unit child 0 0 parent 12um 192um; identify X_r32_c02
rectangle metal4 11.070 191.800 11.470 195.200
getcell mim_unit child 0 0 parent 18um 192um; identify X_r32_c03
rectangle metal4 17.070 191.800 17.470 195.200
getcell mim_unit child 0 0 parent 24um 192um; identify X_r32_c04
rectangle metal4 23.070 191.800 23.470 195.200
rectangle metal3 3.570 190.300 26.430 193.700
rectangle metal4 -4.000 194.800 23.470 195.200
via45 -4 195
rectangle metal3 26.120 6.000 26.420 192.000
rectangle metal5 -4.800 8.200 -3.200 195.800
rectangle metal5 10.470 9.000 12.070 201.000
pin TOP 1 metal3 8.17 6
pin BIT 2 metal5 -4 195
pin AGG 3 metal5 11.27 200
save p1cdac3_m5_inside
select top cell
expand
drc on
drc style drc(full)
drc check
drc catchup
puts "CONTROL_DRC_COUNT inside [drc list count total]"
puts "CONTROL_DRC_DETAILS inside [drc listall why]"
gds write p1cdac3_m5_inside.gds
drc off
flatten p1cdac3_m5_inside_flat
load p1cdac3_m5_inside_flat
save p1cdac3_m5_inside_flat
extract all
ext2spice lvs
ext2spice -o p1cdac3_m5_inside.lvs.spice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o p1cdac3_m5_inside.cap.spice
quit -noprompt
