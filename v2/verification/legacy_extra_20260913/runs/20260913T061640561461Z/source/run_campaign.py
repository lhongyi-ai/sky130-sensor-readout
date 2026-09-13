#!/usr/bin/env python3
"""Local ngspice counterpart of the 32 school extra jobs; never Cadence evidence.

Run in the existing EDA container under /repo. Each run is append-only.
The exported school MOS diffusion geometry is preserved explicitly.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'cadence/project1/basic_design'
PDK = Path('/foss/pdks/sky130A/libs.tech/ngspice/sky130.lib.spice')
NATIVE = ROOT / 'cadence/project1/reports/basic_20260913T023544Z_5cc09eef/received/runs/P01_ac/20260913T015526Z_53d3402e/native_netlist.scs'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def export_csv(p, x, y):
    with p.open('w') as f:
        w = csv.writer(f); w.writerow(['x', 'real', 'imag'])
        w.writerows((float(a), float(complex(b).real), float(complex(b).imag)) for a, b in zip(x, y))


def data(p):
    a = np.loadtxt(p, skiprows=1, ndmin=2)
    if not a.size or not np.all(np.isfinite(a)):
        raise ValueError('Missing/nonfinite data: ' + str(p))
    return a


def render(job, design, native, ports, out, audit):
    dut = design['cells']['p1b_ota_legacy_r4']
    core = ['.subckt p1b_ota_legacy_r4 ' + ' '.join(dut['ports'])]
    devices = []
    for inst in dut['instances']:
        name, kind, pins, prop = inst['name'], inst['cell'], list(inst['terminals'].values()), inst['props']
        if kind in ['nfet_01v8', 'pfet_01v8']:
            got = native['p1b_ota_legacy_r4'][name]
            if got['nets'] != pins or got['model'] != kind:
                raise ValueError('Native topology mismatch ' + name)
            vals = {k: audit.numeric(got['props'][k]) for k in ['w', 'l', 'as', 'ad', 'ps', 'pd', 'm']}
            if not math.isclose(vals['w'], audit.numeric(prop['w']), rel_tol=1e-10) or not math.isclose(vals['l'], audit.numeric(prop['l']), rel_tol=1e-10) or vals['m'] != 1:
                raise ValueError('Native dimensions mismatch ' + name)
            # Wrapper geometry is in um / um^2 under scale=1e-6.
            geom = ' '.join(f'{k}={vals[k] / (1e-12 if k in ["as", "ad"] else 1e-6):.15g}' for k in ['w', 'l', 'as', 'ad', 'ps', 'pd'])
            core.append('X' + name + ' ' + ' '.join(pins) + ' sky130_fd_pr__' + kind + ' ' + geom + ' nf=1 mult=1')
            devices.append((name, kind))
        else:
            core.append(name + ' ' + ' '.join(pins) + ' ' + prop['r' if kind == 'res' else 'c'])
    core.append('.ends p1b_ota_legacy_r4')
    rows = ['* LOCAL NGSPICE COUNTERPART; NOT A CADENCE RUN', f'.lib "{PDK}" {job["corner"]}', f'.temp {job["temp"]}', '.options reltol=1e-5 abstol=1e-12 vntol=1e-7', *core]
    params = job['params']
    allnets = set()
    for inst in design['cells'][job['cell']]['instances']:
        name, kind, pins, prop = inst['name'], inst['cell'], list(inst['terminals'].values()), inst['props']
        allnets.update(pins)
        prefix = name + ' ' + ' '.join(pins) + ' '
        value = lambda s: f'{audit.numeric(s, params):.16g}'
        if kind == 'vdc':
            tail = 'DC ' + value(prop['vdc']) + ' AC ' + value(prop.get('acm', '0')) + ' ' + value(prop.get('acp', '0'))
        elif kind == 'vpulse':
            tail = 'PULSE(' + ' '.join(prop[k] for k in ['val0', 'val1', 'delay', 'rise', 'fall', 'width', 'period']) + ')'
        elif kind == 'idc': tail = value(prop['idc'])
        elif kind in ['res', 'cap', 'ind']: tail = value(prop[{'res':'r', 'cap':'c', 'ind':'l'}[kind]])
        elif kind == 'p1b_ota_legacy_r4': tail = kind
        else: raise ValueError('Unsupported cell ' + kind)
        rows.append(prefix + tail)
    nodes = ['VDD', 'VSS', 'VINP', 'VOUT', 'VBP'] + (['VINN'] if 'VINN' in allnets else [])
    node_expr = [f'v({n})' for n in nodes] + ['i(VDD)']
    op_expr = []
    for name, kind in devices:
        op_expr += [f'@m.xota.x{name.lower()}.msky130_fd_pr__{kind}[{k}]' for k in ['id', 'gm', 'gds', 'vgs', 'vds', 'vdsat']]
    rows += ['.control', 'set noaskquit', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=15', 'op', 'wrdata op.tsv ' + ' '.join(node_expr + op_expr)]
    a = job['analysis']
    if a == 'ac':
        rows += ['ac dec 120 1 1G']
        for n in ['VOUT', 'VINP', 'VINN', 'VDD', 'VSS']:
            rows += [f'let r_{n}=real(v({n}))', f'let i_{n}=imag(v({n}))', f'wrdata {n}.tsv r_{n} i_{n}']
    elif a == 'step':
        rows += ['tran .5n 5u 0 .5n', 'wrdata VINP.tsv v(VINP)', 'wrdata VOUT.tsv v(VOUT)']
    elif a == 'swing':
        rows += ['dc VINP 0 1.8 .01', 'wrdata VINP.tsv v(VINP)', 'wrdata VOUT.tsv v(VOUT)']
    elif a == 'noise':
        rows += ['noise v(VOUT,VSS) VINP dec 100 10 1Meg', 'setplot noise1', 'wrdata noise.tsv onoise_spectrum inoise_spectrum']
    else: raise ValueError(a)
    rows += ['echo LOCAL_ANALYSIS_FINISHED', 'quit', '.endc', '.end']
    (out/'deck.spice').write_text('\n'.join(rows) + '\n')
    return nodes, devices, '\n'.join(core)


def convert(out, job, nodes, devices):
    a = data(out/'op.tsv')[0, 1:]
    names = nodes + ['ivdd']
    with (out/'op.csv').open('w') as f:
        w=csv.writer(f); w.writerow(['name','value']); w.writerows(zip(names, a[:len(names)]))
    b = a[len(names):].reshape(len(devices), 6)
    with (out/'op_devices.csv').open('w') as f:
        w=csv.writer(f); w.writerow(['device','ids','gm','gds','vgs','vds','vdsat'])
        w.writerows([name, *vals] for (name, _), vals in zip(devices, b))
    if job['analysis'] == 'noise':
        n=data(out/'noise.tsv'); export_csv(out/'out.csv',n[:,0],n[:,1]); export_csv(out/'in.csv',n[:,0],n[:,2])
    else:
        for name in (['VOUT','VINP','VINN','VDD','VSS'] if job['analysis']=='ac' else ['VOUT','VINP']):
            n=data(out/(name+'.tsv')); y=n[:,1]+1j*n[:,2] if job['analysis']=='ac' else n[:,1]
            export_csv(out/(name+'.csv'),n[:,0],y)


def run():
    ap=argparse.ArgumentParser(); ap.add_argument('--smoke',action='store_true'); args=ap.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    campaign=HERE/'runs'/stamp; campaign.mkdir(parents=True)
    snapshot=campaign/'source'; snapshot.mkdir()
    source_paths=[Path(__file__),BASE/'design.json',BASE/'jobs.json',BASE/'analyze.py',BASE/'audit.py',BASE/'size_mapping.json',NATIVE,ROOT/'docs/specification.md']
    sources={}
    for p in source_paths:
        shutil.copy2(p,snapshot/p.name); sources[str(p.relative_to(ROOT))]=sha(p)
    put(campaign/'sources.json',sources)
    design=json.loads((snapshot/'design.json').read_text())
    jobs=json.loads((snapshot/'jobs.json').read_text())
    support=next(j for j in jobs if j['id']=='P01_ac').copy(); support['id']='support_nominal_ac'
    jobs=[support]+([] if args.smoke else [j for j in jobs if j['group']=='extra'])
    audit=module('legacy_audit_snapshot',snapshot/'audit.py')
    analysis=module('legacy_analysis_snapshot',snapshot/'analyze.py')
    native,ports=audit.parse((snapshot/'native_netlist.scs').read_text())
    env=dict(simulator=subprocess.check_output(['ngspice','--version'],text=True),model_library=str(PDK.resolve()),model_library_sha256=sha(PDK),sources=sources)
    # Bind every include reachable from the tt entry to content, not merely the small entry file.
    dependency_hashes={}
    def walk(p):
        p=p.resolve()
        if str(p) in dependency_hashes: return
        dependency_hashes[str(p)]=sha(p)
        for line in p.read_text(errors='replace').splitlines():
            m=re.match(r'(?i)\s*\.(?:include|inc)\s+["\']?([^"\'\s]+)',line)
            if m:
                child=Path(m[1]); walk(child if child.is_absolute() else p.parent/child)
    walk(PDK)
    env['model_dependency_sha256']=dependency_hashes; put(campaign/'environment.json',env)
    results=[]; core_hash=None
    for job in jobs:
        out=campaign/job['id']; out.mkdir(); put(out/'job.json',job)
        nodes,devices,core=render(job,design,native,ports,out,audit)
        h=hashlib.sha256(core.encode()).hexdigest()
        if core_hash and h!=core_hash: raise ValueError('DUT changed between jobs')
        core_hash=h; started=time.monotonic()
        with (out/'launcher.log').open('w') as f:
            p=subprocess.run(['ngspice','-b','-o','simulation.log','deck.spice'],cwd=out,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        log=(out/'simulation.log').read_text(errors='replace')
        diagnostics=[l for l in log.splitlines() if re.search(r'warning|error|failed|singular|timestep too small',l,re.I)]
        status=dict(job_id=job['id'],simulator='ngspice',cadence_executed=False,exit_code=p.returncode,elapsed_s=time.monotonic()-started,core_sha256=h,diagnostics=diagnostics,complete_marker='LOCAL_ANALYSIS_FINISHED' in log)
        try:
            if p.returncode or not status['complete_marker'] or re.search(r'timestep too small|fatal error|Error:',log,re.I): raise ValueError('Simulation/log failure')
            convert(out,job,nodes,devices)
            metrics=analysis.analyze(out,job)
            metrics['notes']=[n for n in metrics['notes'] if 'Verify Spectre' not in n]
            metrics['notes']+=['Actual local ngspice execution using school-mapped dimensions and explicit native diffusion geometry; no Spectre run claimed.']
            put(out/'metrics.json',metrics); status['execution_status']='COMPLETE'; status['legacy_job_status']=metrics['status']
        except Exception as exc:
            status['execution_status']='ERROR'; status['error']=str(exc)
        put(out/'status.json',status); results.append(status)
        print(json.dumps(status,ensure_ascii=False),flush=True)
    unchanged=all(sha(ROOT/p)==s for p,s in sources.items())
    report=dict(status='LOCAL_EXECUTION_COMPLETE' if unchanged and all(s['execution_status']=='COMPLETE' for s in results) else 'INCOMPLETE',cadence_execution_status='NOT_RUN_LOCALLY',extra_jobs=sum(j['group']=='extra' for j in jobs),source_unchanged=unchanged,results=results)
    put(campaign/'execution.json',report)
    put(campaign/'manifest.json',{str(p.relative_to(campaign)):sha(p) for p in sorted(campaign.rglob('*')) if p.is_file() and '__pycache__' not in str(p) and p.name!='manifest.json'})
    print(str(campaign),flush=True)
    return 0 if report['status']=='LOCAL_EXECUTION_COMPLETE' else 2


if __name__=='__main__':
    raise SystemExit(run())
