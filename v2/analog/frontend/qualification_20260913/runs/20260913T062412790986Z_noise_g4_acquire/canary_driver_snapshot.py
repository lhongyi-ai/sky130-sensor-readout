#!/usr/bin/env python3
"""Small local integration canary; no school launcher or PDK-path discovery."""
import run_qualification as q
import numpy as np

def deck(gain,state):
    lines=q.base(4,'acquire')
    lines=[x for x in lines if not x.startswith(('VINP ','VINN '))]
    lines +=['VSW SW 0 dc 0 ac 1','BSP VINP 0 V={.9+v(SW)/8}','BSN VINN 0 V={.9-v(SW)/8}']+q.dut()
    lines+=q.control()+['op','wrdata op.dat v(op) v(on) v(fp) v(fn) v(xpga.xota.ncm) v(xpga.xota.cms) i(vdd) i(vcm)','ac lin 1 1k 1k','let differential_gain=mag(v(fp)-v(fn))','wrdata ac.dat differential_gain','dc VSW -.32 .32 .32','wrdata dc.dat v(sw) v(fp) v(fn) i(vdd) i(vcm)']+q.end()
    return '\n'.join(lines)+'\n',None

def analyze(folder,gain):
    op=np.loadtxt(folder/'op.dat',skiprows=1,ndmin=2);ac=np.loadtxt(folder/'ac.dat',skiprows=1,ndmin=2);dc=np.loadtxt(folder/'dc.dat',skiprows=1,ndmin=2)
    if dc.shape!=(3,6) or not all(np.isfinite(x).all() for x in (op,ac,dc)):raise ValueError('Canary data incomplete')
    return {'status':'LOCAL_G4_CANARY_COMPLETE','dc_targets_v':dc[:,1].tolist(),'dc_differential_outputs_v':(dc[:,2]-dc[:,3]).tolist(),'zero_output_common_mode_v':float((op[0,3]+op[0,4])/2),'ac_1khz_target_to_output_gain':float(ac[0,1]),'school_cadence_run':False,'candidate_phase':'acquire','scope':'Connectivity/reference values only, not frontend qualification.'}

if __name__=='__main__':
    q.noise_deck=deck;q.analyze_noise=analyze
    q.run('noise',4,'acquire',45)
