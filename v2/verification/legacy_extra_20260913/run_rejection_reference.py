#!/usr/bin/env python3
"""Additional differential AC at the *same* OP as CM/PSRR/noise benches."""
import copy
import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import run_campaign as r


def main():
    out=r.HERE/'rejection_reference'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    design=json.loads((r.BASE/'design.json').read_text())
    jobs=json.loads((r.BASE/'jobs.json').read_text())
    job=copy.deepcopy(next(j for j in jobs if j['id']=='P01_ac'))
    job['id']='same_op_differential_ac'; job['group']='support'
    design['cells']['p1b_tb_ac']=copy.deepcopy(design['cells']['p1b_tb_cm'])
    for i in design['cells']['p1b_tb_ac']['instances']:
        if i['name'] in ['VINP','VINN']:
            i['props']['acm']='0.5'; i['props']['acp']='180' if i['name']=='VINN' else '0'
    r.put(out/'design.json',design); r.put(out/'job.json',job)
    for src in [Path(__file__),r.HERE/'run_campaign.py',r.BASE/'audit.py',r.BASE/'analyze.py',r.NATIVE]: shutil.copy2(src,out/src.name)
    audit=r.module('reference_audit',out/'audit.py'); analysis=r.module('reference_analysis',out/'analyze.py')
    native,ports=audit.parse(r.NATIVE.read_text())
    nodes,devices,core=r.render(job,design,native,ports,out,audit)
    started=time.monotonic()
    with (out/'launcher.log').open('w') as f:
        proc=subprocess.run(['ngspice','-b','-o','simulation.log','deck.spice'],cwd=out,stdout=f,stderr=subprocess.STDOUT,timeout=180)
    log=(out/'simulation.log').read_text()
    if proc.returncode or 'LOCAL_ANALYSIS_FINISHED' not in log: raise RuntimeError('Reference failed')
    r.convert(out,job,nodes,devices)
    r.put(out/'metrics.json',analysis.analyze(out,job))
    r.put(out/'status.json',dict(execution_status='COMPLETE',exit_code=proc.returncode,elapsed_s=time.monotonic()-started,core_sha256=hashlib.sha256(core.encode()).hexdigest(),cadence_executed=False))
    r.put(out/'manifest.json',{str(p.relative_to(out)):r.sha(p) for p in out.rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.name!='manifest.json'})
    print(out)


if __name__=='__main__': main()
