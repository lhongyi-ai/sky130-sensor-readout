#!/usr/bin/env python3
"""Measure actual installed PDK passives; no guessed resistance/cap density."""
import json
import numpy as np
from run_frontend import HERE, LIB, run_deck
folder=HERE/"results/passives_w5p73"
folder.mkdir(parents=True,exist_ok=True)
text=f"""* Installed SKY130 passive geometry qualification, not layout DRC.
.lib {LIB} tt
.temp 27
V1 R1 0 1
V2 R2 0 1
VC C1 0 dc 0 ac 1
XR1 R1 0 0 sky130_fd_pr__res_high_po_5p73 L=10
XR2 R2 0 0 sky130_fd_pr__res_high_po_5p73 L=50
XC C1 0 sky130_fd_pr__cap_mim_m3_1 W=44.5 L=44.5
.control
set wr_singlescale
set wr_vecnames
op
let r1=-1/i(v1)
let r2=-1/i(v2)
wrdata resistor.dat r1 r2
ac lin 1 1000 1000
let ceff=-imag(i(vc))/(2*pi*1000)
wrdata capacitor.dat ceff
quit
.endc
.end
"""
run_deck("passives",text,folder)
r=np.loadtxt(folder/"resistor.dat",skiprows=1,ndmin=2)[0]
c=np.loadtxt(folder/"capacitor.dat",skiprows=1,ndmin=2)[0]
slope=(r[2]-r[1])/40
intercept=r[1]-10*slope
result={"model":"sky130_fd_pr__res_high_po_5p73", "width_um":5.73,
 "r_l10_ohm":float(r[1]),"r_l50_ohm":float(r[2]),
 "r_slope_ohm_per_um":float(slope),"r_intercept_ohm":float(intercept),
 "nominal_lengths_um":{str(target):float((target-intercept)/slope) for target in [275,2150,2000,9650,10000,40000,160000]},
 "mim44p5um_square_effective_cap_f":float(c[1]),
 "caution":"These are TT electrical fits, not physical-layout/DRC or resistor voltage-coefficient signoff."}
(folder/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
