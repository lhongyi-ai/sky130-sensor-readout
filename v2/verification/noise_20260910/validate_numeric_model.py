#!/usr/bin/env python3
"""Cross-check numeric extraction itself with ngspice's original BSIM4v5.

This uses the same 349 explicitly supplied parameters and extracted geometry;
the PDK-derived deck remains in /tmp. It never changes the model version.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from rawfile import rawread

from probe import HERE, run


def main():
    folder=Path(sys.argv[1]).resolve()
    report=json.loads((folder/'summary.json').read_text())
    temp=Path(report['numeric_model_runtime_path']).parent
    original=json.loads((temp/'parsed_parameters.json').read_text())
    parameters=original['model_values'];instance=original['instance_values']
    # Keep LEVEL and VERSION in ngspice, and all explicit PDK parameters.
    modelargs=' '.join(f'{k}={v if isinstance(v,str) else format(v,".17g")}' for k,v in parameters.items())
    instanceargs=' '.join(f'{k}={v:.17g}' for k,v in instance.items())
    deck=f'''Independent native check of fully evaluated SKY130 bin; no changed version
.options scale=1 reltol=1e-6 vntol=1e-10 abstol=1e-15
.model selected nmos {modelargs}
VDD vdd 0 1.8
VG gate 0 DC .7 AC 1
RLOAD vdd out 20k
CLOAD out 0 1p
M1 out gate 0 0 selected {instanceargs}
.temp 27
.control
set wr_vecnames
set wr_singlescale
set numdgt=17
op
wrdata {folder/'flat_ngspice_op.tsv'} v(out) i(vdd)
ac dec 40 10 100meg
wrdata {folder/'flat_ngspice_ac.tsv'} real(v(out)) imag(v(out))
noise v(out) vg dec 40 10 100meg
setplot noise1
wrdata {folder/'flat_ngspice_noise.tsv'} onoise_spectrum
quit
.endc
.end
'''
    source=temp/'flat_ngspice.spice';source.write_text(deck)
    status=run(['ngspice','-b',str(source)],temp,folder/'flat_ngspice.log')
    result={'status':'NUMERIC_EXTRACTION_NOT_VERIFIED','run':status,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_runtime_path':str(source),'same_model_version':parameters['version'],
            'all_original_explicit_model_parameters_preserved':True}
    if status['returncode']==0:
        op=np.loadtxt(folder/'flat_ngspice_op.tsv',skiprows=1)
        ac=np.loadtxt(folder/'flat_ngspice_ac.tsv',skiprows=1)
        noise=np.loadtxt(folder/'flat_ngspice_noise.tsv',skiprows=1)
        original_ac=np.load(folder/'ngspice_ac.npz')
        original_noise=np.load(folder/'ngspice_noise.npz')
        reference_psd=original_noise['amplitude_spectrum']**2
        flat_psd=noise[:,1]**2
        flat_ac=ac[:,1]+1j*ac[:,2]
        input_ac=original_ac['voltage']
        dc_err=float(abs(op[2]/report['ngspice_op']['vdd#branch']-1))
        ac_err=float(np.max(np.abs(flat_ac/input_ac-1)))
        noise_err=float(np.max(np.abs(flat_psd/reference_psd-1)))
        result.update(dc_current_relative_error=dc_err,max_ac_complex_relative_error=ac_err,
                      max_noise_psd_relative_error=noise_err,
                      native_bin_extraction_equivalent_at_tested_bias=dc_err<1e-6 and ac_err<1e-6 and noise_err<1e-6)
        if result['native_bin_extraction_equivalent_at_tested_bias']:
            result['status']='NUMERIC_EXTRACTION_NATIVE_EQUIVALENCE_PASS_SINGLE_BIAS'
        vacac=rawread(str(folder/'ac1.raw')).get()
        vacfreq=vacac['frequency'].real
        reference_ac=np.interp(vacfreq,original_ac['frequency'],input_ac.real)+1j*np.interp(vacfreq,original_ac['frequency'],input_ac.imag)
        result['vacask_ac_max_relative_error']=float(np.max(np.abs(vacac['out']/reference_ac-1)))
        result['vacask_unknown_version_fallback']=report['unknown_version_fallback']
        result['vacask_noise_max_error_db']=float(np.max(np.abs(10*np.log10(report['noise_psd_ratio_minmax']))))
        result['vacask_model_equivalence_qualified']=False
    (folder/'numeric_equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
