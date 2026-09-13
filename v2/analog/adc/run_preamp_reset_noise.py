#!/usr/bin/env python3
"""Nominal stationary preamp noise with a physically reset StrongARM load.

The retained SR latch is omitted from this fixture, so an arbitrary symmetric
latch DC solution cannot contaminate the noise result. This does not claim to
model clocked comparator noise or cyclostationary noise folding.
"""
import hashlib
import json

import numpy as np

from run_adc import HERE, RESULTS, deck, prepare, run_case, table


def main():
    prepare();name='preamp_reset_strongarm_noise'
    body=f'''.include {HERE/'adc_preamp.spice'}
.options sparse
VDD vdd 0 1.8
VCMP cmpdd 0 1.8
VCM cm 0 .9
VDIFF diff 0 DC 0 AC 1
EIP ip cm diff 0 .5
EIN inn cm diff 0 -.5
XPRE ip inn op on vdd 0 adc_preamp
XSA op on dp dn 0 cmpdd 0 adc_strongarm
XDP dp 0 adc_mim_bank COUNT=16
XDN dn 0 adc_mim_bank COUNT=16
'''
    control=f'''op
wrdata {RESULTS/(name+'_op.tsv')} v(op) v(on) i(vdd) i(vcmp)
ac lin 1 1 1
let dg=v(op)-v(on)
wrdata {RESULTS/(name+'_ac.tsv')} real(dg) imag(dg)
noise v(op,on) VDIFF dec 40 1 100meg
setplot noise1
wrdata {RESULTS/(name+'_noise.tsv')} onoise_spectrum inoise_spectrum
'''
    run_case(name,deck(name,body,control));op=table(name+'_op')[0];ac=table(name+'_ac')[0];n=table(name+'_noise')
    gain=float(np.hypot(ac[1],ac[2]));bands=[]
    for upper in [5e3,50e3,1e8]:
        m=n[:,0]<=upper
        bands.append(dict(lower_hz=1,upper_hz=upper,output_noise_referred_to_dc_input_rms_v=float(np.sqrt(np.trapezoid(n[m,1]**2,n[m,0]))/gain),
                          integrated_input_equivalent_spectrum_rms_v=float(np.sqrt(np.trapezoid(n[m,2]**2,n[m,0])))))
    result=dict(evidence_level='Nominal stationary preamp noise, real reset StrongARM plus MIM load, no SR latch DC ambiguity; NOT ADC noise qualification',
                vdd=1.8,temperature_c=27,corner='tt',dc_gain_vv=gain,preamp_power_w=float(-1.8*op[3]),
                reset_strongarm_static_power_w=float(-1.8*op[4]),noise_bands=bands,
                source_sha256={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ['adc_blocks.spice','adc_preamp.spice']},
                limitations=['No clocked comparator noise','No sampled-noise folding','No noise below 1 Hz included',
                             'No mismatch or extracted parasitics','Output-buffer gate parasitics omitted from reset comparator ballast load'])
    (RESULTS/'preamp_reset_noise_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
