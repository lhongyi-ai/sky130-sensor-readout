#!/usr/bin/env python3
"""Check actual export coverage and the PMOS adapter against school evidence."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import build_report as b


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('campaign',type=Path); args=ap.parse_args()
    p=args.campaign.resolve(); checked=b.verify(p); checks=[]
    expected={j['id'] for j in b.load(p/'source/jobs.json') if j['group']=='extra'}
    actual={j.parent.name for j in p.glob('*/job.json') if b.load(j)['group']=='extra'}
    assert actual==expected and len(actual)==32
    for name in sorted(actual|{'support_nominal_ac'}):
        out=p/name; job=b.load(out/'job.json'); a=job['analysis']
        for field in (['VOUT','VINP','VINN','VDD','VSS'] if a=='ac' else (['in','out'] if a=='noise' else ['VINP','VOUT'])):
            x,y=b.curve(out,field)
            if a=='ac': assert len(x)==1081 and abs(x[0]-1)<1e-10 and abs(x[-1]/1e9-1)<1e-10
            elif a=='noise': assert len(x)==501 and abs(x[0]-10)<1e-10 and abs(x[-1]/1e6-1)<1e-10
            elif a=='step': assert x[0]<=1e-14 and abs(x[-1]-5e-6)<1e-14 and max(np.diff(x))<=.5e-9*(1+1e-8)
            else: assert len(x)==181 and abs(x[0])<1e-12 and abs(x[-1]-1.8)<1e-10
        with (out/'op_devices.csv').open() as f: devices=list(csv.DictReader(f))
        assert len(devices)==13 and len({d['device'] for d in devices})==13
        assert all(np.isfinite(float(v)) for d in devices for k,v in d.items() if k!='device')
        checks.append(dict(job=name,coverage='PASS',OP_devices=13))
    school=b.ROOT/'cadence/project1/reports/basic_20260913T023544Z_5cc09eef/received/runs/P01_ac/20260913T015526Z_53d3402e'
    def devices(path):
        with path.open() as f:return {r['device']:r for r in csv.DictReader(f)}
    local=devices(p/'support_nominal_ac/op_devices.csv'); reference=devices(school/'op_devices.csv')
    worst={}
    for k in ['ids','gm','gds','vds','vdsat']:
        differences=[abs(float(d[k])-float(reference[n][k]))/max(abs(float(reference[n][k])),1e-12) for n,d in local.items()]
        worst[k]=max(differences)
        assert worst[k]<0.001,(k,worst[k])
    result=dict(status='PASS_RAW_COVERAGE_AND_BASELINE_ADAPTER',manifest_entries_verified=checked,job_checks=checks,all_13_device_baseline_relative_errors=worst,unpaired_local_fields=['vgs: not exported by the school source'],first_check_attempt='Exited 1 with KeyError vgs: initial checker assumed a school CSV field that was not exported. Corrected to compare the five fields actually present; no waveform or circuit changed.',limitations='Data and adapter validation only; device operating-region failures at ICMR edges are preserved, not overridden.')
    b.put(b.HERE/('evidence_check_'+p.name+'.json'),result)
    print(json.dumps({'status':result['status'],'jobs_checked':len(checks),'worst_device_relative_error':max(worst.values())}))


if __name__=='__main__': main()
