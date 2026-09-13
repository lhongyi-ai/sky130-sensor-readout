#!/usr/bin/env python3
"""Read-only settling-window analysis of the already frozen C waveforms."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from measurement_evidence import verify_manifest,write_manifest


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    rows=[]
    for path in sorted((HERE/'diagnostics').glob('*headroom_c*/summary.json')):
        folder=path.parent
        if not verify_manifest(folder):raise ValueError('Source waveform lacks immutable evidence')
        summary=json.loads(path.read_text())
        if summary['status']!='DIAGNOSTIC_COMPLETE':raise ValueError('Incomplete experiment')
        c={key:i for i,key in enumerate(json.loads((folder/'columns.json').read_text()))}
        dc=np.loadtxt(folder/'dc.dat',skiprows=1)
        target=(dc[:,c['v(sp)']]-dc[:,c['v(sn)']])*summary['gain']
        steady=dc[:,c['v(op)']]-dc[:,c['v(on)']]
        tr=np.loadtxt(folder/'transient.dat',skiprows=1)
        t=tr[:,0];diff=tr[:,-2]-tr[:,-1]
        if not np.isfinite(dc).all() or not np.isfinite(tr).all() or np.any(np.diff(t)<=0):
            raise ValueError('Invalid measured axes or values')
        windows=[]
        for level,onset in ((.36,8e-6),(-.36,13e-6),(0,18e-6)):
            endpoint=onset+2.476847754e-6
            if endpoint<t[0] or endpoint>t[-1]:raise ValueError('Uncovered measurement window')
            dc_value=float(np.interp(level,target,steady))
            actual=float(np.interp(endpoint,t,diff))
            residual=actual-dc_value
            windows.append({'target_output_equivalent_v':level,'step_onset_s':onset,
                            'input_transition_duration_s':10e-9,'elapsed_from_step_onset_s':2.476847754e-6,
                            'measurement_time_s':endpoint,'dc_steady_output_v':dc_value,
                            'transient_filtered_output_v':actual,'dynamic_minus_dc_residual_v':residual,
                            'limit_v':.8/4096*.25,'dynamic_residual_within_0p25_lsb':abs(residual)<=.8/4096*.25})
        rows.append({'source_summary_path':str(path.relative_to(HERE)),
                     'source_summary_sha256':sha(path),'dc_sha256':sha(folder/'dc.dat'),
                     'transient_sha256':sha(folder/'transient.dat'),'source_manifest_sha256':sha(folder/'evidence_manifest.json'),
                     'source_sha256':summary['source_sha256'],'gain':summary['gain'],'windows':windows,
                     'all_static_cap_load_step_windows_pass':all(w['dynamic_residual_within_0p25_lsb'] for w in windows)})
    if {row['gain'] for row in rows}!={1,4,16} or len({row['source_sha256'] for row in rows})!=1:
        raise ValueError('Need all three gains from one identical source')
    folder=HERE/'settling_analysis'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True)
    (folder/'analysis_script_snapshot.py').write_bytes(Path(__file__).read_bytes())
    report={'status':'DERIVED_FROM_EXISTING_FROZEN_WAVEFORMS_NO_NEW_SIMULATION','rows':rows,
            'noise_included':False,'full_frontend_qualified':False,'full_chip_qualified':False,
            'scope':'Static 81.285pF plus4pF per side through realRISO2600; no sampling switch or charge kickback. Residual is relative to the same-candidate DC transfer, separating static gain error.',
            'limitations':['Measurement uses linear interpolation of a maximum5ns-step waveform.',
                           'The2.476847754us interval starts at input transition onset, not after its10ns ramp.',
                           'These failures show that even the easier static-capacitive-load diagnostic is not closed; passing would still not qualify real SAR acquisition.',
                           'Neither per-point calibration nor new fitting is used for this dynamic-minus-DC residual.']}
    out=folder/'summary.json';out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    write_manifest(folder,['summary.json','analysis_script_snapshot.py'],[Path(__file__)])
    print(json.dumps({'path':str(out),'gains':{str(row['gain']):[w['dynamic_minus_dc_residual_v']*1e6 for w in row['windows']] for row in rows}},indent=2))


if __name__=='__main__':main()
