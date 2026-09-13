#!/usr/bin/env python3
"""Series-injection CM loop diagnosis; voltage-return approximation.

The injected source is ONLY in a generated measurement copy. The high-Z MOS
gate break minimizes current-injection error; report as a loop diagnostic,
not unconditional multiloop signoff. Real CM transient checks remain required.
"""
from pathlib import Path
import argparse
import numpy as np
from run_frontend import HERE, header, run_deck

p=argparse.ArgumentParser()
p.add_argument("--core", default="frontend_core.spice")
p.add_argument("--out", default="results/cm_loop")
p.add_argument("--gain",type=int,default=4)
a=p.parse_args()
folder=HERE/a.out
folder.mkdir(parents=True,exist_ok=True)
source=(HERE/a.core).read_text()
source=source.replace("XCMSENSE CMCTL CMSENSE ","XCMSENSE CMCTL CMIN ")
source=source.replace(".ends sky130_v2_frontend", "VLOOP CMIN CMSENSE dc 0 ac 1\n.ends sky130_v2_frontend")
core=folder/"injected_core.spice"
core.write_text(source)
text=header("tt",1.8,27,core)+f"""
VIP SP 0 0.9
VIN SN 0 0.9
RSP SP IP 350
RSN SN IN 350
XPGA IP IN OP ON VDD 0 VCM sky130_v2_pga RF={a.gain*10000}
CLP OP 0 5p
CLN ON 0 5p
.control
set wr_singlescale
set wr_vecnames
op
ac dec 100 1 1g
let ret=-v(xpga.xamp.cmsense)/v(xpga.xamp.cmin)
let mag=db(ret)
let ph=180/pi*cph(ret)
wrdata cm_loop.dat mag ph
quit
.endc
.end
"""
run_deck("cm_loop",text,folder)
v=np.loadtxt(folder/"cm_loop.dat",skiprows=1)
print("DC loop dB/phase",v[0])
for i in np.flatnonzero(np.diff(np.sign(v[:,1]))):
 print("Crossover",v[i],"phase margin deg",180+v[i,2])
