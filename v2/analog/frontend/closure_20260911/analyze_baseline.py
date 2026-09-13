#!/usr/bin/env python3
"""Read all 45 immutable G16 cases; identify compression and headroom patterns."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
FRONT=HERE.parent
REPAIR=FRONT/'repair_20260910'
INDEX=REPAIR/'qualification_g16_pvt/20260910T065530849637Z/summary.json'
sys.path.insert(0,str(FRONT))
from measurement_evidence import verify_manifest,write_manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    index=json.loads(INDEX.read_text())
    rows=[]
    for item in index['cases']:
        folder=REPAIR/item['path']
        if not verify_manifest(folder):
            raise ValueError('Baseline case lacks immutable evidence: '+str(folder))
        s=json.loads((folder/'summary.json').read_text())
        data=np.loadtxt(folder/'linearity.dat',skiprows=1)
        if len(data)!=81 or not np.isfinite(data).all():
            raise ValueError('Baseline coverage/data changed')
        target=data[:,1]*16
        raw=data[:,2]
        fit=np.asarray(s['calibration_coefficients'])
        residual=(raw*fit[0]+fit[1]-target)/(.8/4096)
        hold=np.ones(81,dtype=bool);hold[[8,40,72]]=False
        worst=int(np.flatnonzero(hold)[np.argmax(abs(residual[hold]))])
        op_path=folder/'op_nodes.dat'
        names=op_path.open().readline().split()
        op=dict(zip(names,np.loadtxt(op_path,skiprows=1,ndmin=2)[0]))
        def node(name):return float(op['xpga.xamp.'+name])
        row={key:s[key] for key in ('gain','corner','vdd_v','temp_c','calibration_coefficients')}
        row.update(case_path=str(folder.relative_to(FRONT)),summary_sha256=sha(folder/'summary.json'),
                   raw_sha256=sha(folder/'linearity.dat'),op_sha256=sha(op_path),
                   source_sha256=sha(folder/'frontend_pdk_snapshot.spice'),
                   manifest_sha256=sha(folder/'evidence_manifest.json'),manifest_verified=True,
                   max_holdout_error_lsb=float(np.max(abs(residual[hold]))),
                   worst_signed_residual_lsb=float(residual[worst]),worst_target_v=float(target[worst]),
                   residual_at_output_equivalent_v={str(round(float(target[k]),2)):float(residual[k]) for k in (0,8,20,40,60,72,80)},
                   residual_even_component_max_lsb=float(np.max(abs((residual+residual[::-1])/2))),
                   raw_output_endpoints_v=[float(raw[0]),float(raw[-1])],
                   local_output_per_target_slope_zero=float((raw[41]-raw[39])/(target[41]-target[39])),
                   local_output_per_target_slope_positive_edge=float((raw[80]-raw[78])/(target[80]-target[78])),
                   max_output_cm_error_v=float(np.max(abs(data[:,3]-s['vdd_v']/2))),
                   zero_nodes_v={key:node(key) for key in ('xp','xn','npc','nnc','xerrp.tail','xerrp.ts','bt','bcasc','bn')},
                   zero_input_vds_v=node('npc')-node('xerrp.tail'),
                   zero_upper_tail_vds_v=node('xerrp.tail')-node('xerrp.ts'),
                   static_accuracy_limit_lsb=1 if (s['vdd_v'],s['temp_c'])==(1.8,27) else 4)
        row['static_accuracy_pass']=row['max_holdout_error_lsb']<=row['static_accuracy_limit_lsb']
        rows.append(row)
    coordinates={(r['corner'],r['vdd_v'],r['temp_c']) for r in rows}
    if len(rows)!=45 or len(coordinates)!=45:
        raise ValueError('Index must include all 45 unique PVT combinations')
    groups={}
    for field in ('corner','vdd_v','temp_c'):
        grouped=defaultdict(list)
        for row in rows:grouped[str(row[field])].append(row)
        groups[field]={key:{'case_count':len(group),'static_failures':sum(not r['static_accuracy_pass'] for r in group),
                            'worst_holdout_lsb':max(r['max_holdout_error_lsb'] for r in group),
                            'minimum_zero_input_vds_v':min(r['zero_input_vds_v'] for r in group),
                            'minimum_zero_upper_tail_vds_v':min(r['zero_upper_tail_vds_v'] for r in group)}
                       for key,group in grouped.items()}
    folder=HERE/'baseline_analysis'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True)
    (folder/'analysis_script_snapshot.py').write_bytes(Path(__file__).read_bytes())
    report={'status':'ALL_45_BASELINE_CASES_ANALYZED','input_index_path':str(INDEX.relative_to(FRONT)),
            'input_index_sha256':sha(INDEX),'case_count':45,'groups':groups,'cases':rows,
            'findings':[
                'Every point retains the original per-corner nominal three-anchor coefficients; there is no new VT refit.',
                'The largest failures are odd-symmetric amplitude compression, not a large static differential offset.',
                'High-voltage/hot input-pair drain-source headroom collapses because the ground-referenced diode-stack drain-cascode bias does not track the signal common mode.',
                'FS low-voltage/cold also has inadequate upper-tail headroom; one drain-bias correction alone cannot establish all-gain closure.',
                'Saved baseline node operating points are at zero differential only; VDS minus VDSAT and full-range device regions require separate frozen diagnostic runs.',
                'DC equilibrium is not stability, noisy dynamic precision, or whole-chip qualification.'],
            'full_frontend_qualified':False,'full_chip_qualified':False}
    output=folder/'summary.json'
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    write_manifest(folder,['summary.json','analysis_script_snapshot.py'],[Path(__file__)])
    print(json.dumps({'path':str(output),'groups':groups},indent=2))


if __name__=='__main__':main()
