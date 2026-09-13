#!/usr/bin/env python3
"""Recompute historical sampling metrics without rewriting original evidence."""
import json
import re
import numpy as np
from run_frontend import HERE,validate_log
from measurements import checked_data,interval_stats

LSB=.8/4096
def assess(raw,vdd,width_us,log,power_is_current,power_start):
    validate_log(log)
    data=checked_data(raw,40e-6)
    samples=[]
    for start in [10,20,30]:
        end=(start+width_us)*1e-6-10e-9
        ref,ripple=interval_stats(data[:,0],data[:,1],end+3e-6,end+4e-6)
        pre=float(np.interp(end,data[:,0],data[:,2])-ref)
        post=float(np.interp(end+30e-9,data[:,0],data[:,2])-ref)
        samples.append({'pre_error_v':pre,'post_error_v':post,'reference_v':ref,
                        'reference_peak_to_peak_v':ripple,
                        'pass':abs(pre)<=LSB/4 and abs(post)<=LSB/4 and ripple<=LSB/40})
    cm=float(np.max(abs(data[:,3]-vdd/2)))
    p=None
    if power_is_current and data.shape[1]>7:
        p=interval_stats(data[:,0],-vdd*data[:,7],power_start,40e-6)[0]
    elif not power_is_current:
        p=interval_stats(data[:,0],data[:,4],power_start,40e-6)[0]
    return {'sampling_subset_pass':all(s['pass'] for s in samples) and cm<=.05 and all(.25<abs(s['reference_v'])<.45 for s in samples),
            'time_weighted_vdd_power_w':p,'power_interval_s':[power_start,40e-6],
            'max_common_mode_error_v':cm,'samples':samples}

rows=[]
for raw in sorted((HERE/'results').rglob('sampling.dat')):
    item={'raw_path':str(raw.relative_to(HERE))}
    try:
        deck=(raw.parent/'sampling.spice').read_text()
        vdd=float(re.search(r'^VDD VDD 0 ([\d.]+)$',deck,re.M).group(1))
        clock=next(line for line in deck.splitlines() if line.startswith('VACQ ACQ '))
        width=float(clock.split('PULSE(',1)[1].split(')',1)[0].split()[5][:-1])
        item.update(assess(raw,vdd,width,raw.parent/'sampling.log',True,0))
        item['audit_status']='MEASURED_WITH_INTERPOLATION_AND_STABLE_REFERENCE_GATES'
    except (ValueError,RuntimeError,AttributeError,FileNotFoundError) as exc:
        item.update(audit_status='INVALID_OR_INCOMPLETE',sampling_subset_pass=False,error=str(exc)[:250])
    rows.append(item)

matrix=[]
summary=HERE/'results/gm3x_rz_matrix/summary.json'
if summary.exists():
    for old in json.loads(summary.read_text())['cases']:
        raw=HERE/old['raw_path']
        item={k:old[k] for k in ['raw_path','corner','temp_c','vdd_v','gain']}
        item['previous_sampling_subset_pass']=old['sampling_subset_pass']
        try:
            item.update(assess(raw,old['vdd_v'],2.49,raw.parent/'matrix.log',False,10e-6))
        except (ValueError,RuntimeError,FileNotFoundError) as exc:
            item.update(sampling_subset_pass=False,error=str(exc)[:250])
        matrix.append(item)

report={'purpose':'Independent re-analysis; original reports are retained and not silently overwritten.',
        'current_time_weighted_results':rows,
        'legacy_135_matrix_cases':len(matrix),'legacy_135_matrix_recomputed_passes':sum(r['sampling_subset_pass'] for r in matrix),
        'legacy_135_matrix':matrix,
        'cautions':['Historical simulation tolerances and physical circuit weaknesses are not cured by numerical re-analysis.',
                    'Stable own-endpoint acquisition checks do not establish fixed-calibration accuracy or system SNDR.',
                    'Cases with missing/aborted traces fail; no incomplete waveform is qualified.']}
(HERE/'results/legacy_measurement_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Audited {len(rows)} sampling traces; old135matrix recomputed passes {report["legacy_135_matrix_recomputed_passes"]}/{len(matrix)}')
