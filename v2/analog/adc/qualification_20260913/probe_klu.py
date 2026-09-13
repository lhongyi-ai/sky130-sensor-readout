#!/usr/bin/env python3
"""Bounded KLU operating-point probe; no transient or speedup claim."""
from datetime import datetime,timezone
import json
import os
import re
import shutil
import subprocess
import time
import qualify as q

def main():
    q.verify()
    if (q.HERE/'worker.lock').exists():
        raise ValueError('ADC transient worker still active; run probe sequentially')
    out=q.HERE/'solver_probe'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    source=q.deck_for('baseline')
    head=source.split('.control\n',1)[0].replace('.options sparse ','.options klu ')
    (out/'probe.spice').write_text(head+'.control\nop\noption\nrusage all\nquit\n.endc\n.end\n')
    shutil.copy2(q.HERE/'snapshot/.spiceinit',out/'.spiceinit')
    start=time.monotonic()
    try:
        proc=subprocess.run(['ngspice','-b','-o','native.log','probe.spice'],cwd=out,
            env=dict(os.environ,SPICE_USERINIT_DIR=str(out)),capture_output=True,text=True,timeout=30)
        rc,log=proc.returncode,proc.stdout+proc.stderr
    except subprocess.TimeoutExpired as exc:
        rc=None;log='TIMEOUT\n'+(exc.stdout or b'').decode(errors='replace')+(exc.stderr or b'').decode(errors='replace')
    elapsed=time.monotonic()-start
    if (out/'native.log').exists():log+=(out/'native.log').read_text(errors='replace')
    (out/'probe.log').write_text(log)
    errors=[line for line in log.splitlines() if re.search('error|unsupported|not support|aborted|singular|klu|sparse',line,re.I)]
    result={'status':'OPERATING_POINT_PROBE_ONLY','returncode':rc,'wall_seconds':elapsed,
        'transient_requested':False,'speedup_measured':False,'complete_adc_qualified':False,
        'solver_related_messages':errors,'snapshot_sha256':q.sc.sha(q.HERE/'snapshot/manifest.json'),
        'runner_sha256':q.sc.sha(__file__),
        'official_option_reference':'https://ngspice.sourceforge.io/applic.html',
        'artifact_sha256':{p.name:q.sc.sha(p) for p in out.iterdir() if p.is_file()}}
    q.write(out/'summary.json',result)
    print(json.dumps(result,indent=2));print(str(out))
    return 0 if rc==0 else 2

if __name__=='__main__':raise SystemExit(main())
