#!/usr/bin/env python3
"""Linux entry point. Standard library only. Sequential, immutable attempts."""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from audit import check

ROOT=Path(__file__).resolve().parent
DEFAULT=dict(ocean='/project/engineering/cadence21/ic/tools/dfII/bin/ocean',
             spectre='/project/engineering/cadence21/spectre/tools/bin/spectre',
             workdir=str(Path.home()/'cadence_skywater'),
             model='/project/engineering/cadence21/CDK/sky130_release_0.0.3/models/sky130.lib.spice')
def read(name): return json.loads((ROOT/name).read_text())
def write(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def stamp(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def quote(s): return json.dumps(str(s))  # SKILL string, never shell escaping.
def verify():
    for name,digest in read('package_manifest.json')['files'].items():
        if sha(ROOT/name)!=digest: raise ValueError('Package hash mismatch: '+name)
def config():
    cfg=dict(DEFAULT)
    if (ROOT/'site.json').exists(): cfg.update(read('site.json'))
    return cfg
def invoke(argv,log,cwd,stdin=None):
    # The launcher starts system Python without Cadence's incompatible libpython.
    # Restore the captured library path only in the environment of tool children.
    child_env=dict(os.environ)
    if 'P1_RUNTIME_LD_LIBRARY_PATH' in child_env:
        child_env['LD_LIBRARY_PATH']=child_env.pop('P1_RUNTIME_LD_LIBRARY_PATH')
    with log.open('w') as output:
        try:
            with open(stdin) if stdin else open(os.devnull) as inp:
                return subprocess.run(argv,cwd=cwd,stdin=inp,stdout=output,stderr=subprocess.STDOUT,check=False,env=child_env).returncode
        except OSError as e:
            output.write(str(e)+'\n'); return 127

def native_netlist_path(out):
    """Use the OCEAN-returned top-level location, never recursive name matching."""
    returned=json.loads((out/'netlist_return.txt').read_text())
    if not isinstance(returned,str) or not Path(returned).is_absolute():
        raise OSError('OCEAN did not return an absolute input.scs path')
    native=(out/'native').resolve()
    entry=Path(returned).resolve()
    try:
        relative=entry.relative_to(native)
    except ValueError:
        raise OSError('OCEAN returned a path outside this attempt; refuse stale netlist')
    if entry.name!='input.scs' or entry.parent.name!='netlist' or 'ihnl' in relative.parts:
        raise OSError('Unexpected OCEAN top-level path: '+returned)
    if not entry.is_file():
        raise OSError('OCEAN-returned input.scs is missing: '+returned)
    body=(entry.parent/'netlist').resolve()
    if body.parent!=entry.parent or not body.is_file():
        raise OSError('Top-level native netlist is missing or redirected; see netlist_return.txt')
    # input.scs contains ADE setup/model includes. The sibling netlist is the
    # native circuit body consumed by the existing strict topology/size audit.
    # Keep both as evidence; deck() supplies the frozen job's model and analyses.
    (out/'native_input.scs').write_bytes(entry.read_bytes())
    write(out/'native_selection.json',dict(
        method='OCEAN return input.scs -> same-directory top-level netlist',
        returned_input=str(entry),returned_input_sha256=sha(entry),
        selected_body=str(body),selected_body_sha256=sha(body)))
    return body

def netlist_script(job,out,cfg):
    s='envSetVal("asimenv.startup" "projectDir" \'string '+quote(out/'native')+')\n'
    s+='simulator(\'spectre)\ndesign("project1" '+quote(job['cell'])+' "schematic")\n'
    s+='resultsDir('+quote(out/'native_results')+')\n'
    for name,value in job['params'].items(): s+='desVar('+quote(name)+' '+str(value)+')\n'
    s+='modelFile(list('+quote(cfg['model'])+' '+quote(job['corner'])+'))\ntemp('+str(job['temp'])+')\n'
    s+='p1bNl=createNetlist(?recreateAll t ?display nil)\n'
    s+='unless(p1bNl error("Native netlisting failed"))\n'
    s+='p1bF=outfile('+quote(out/'netlist_return.txt')+')\nfprintf(p1bF "%L\\n" p1bNl)\nclose(p1bF)\nexit()\n'
    return s

def netlist_body(text):
    result=[]; inside=False
    for raw in text.replace('\\\n',' ').splitlines():
        line=raw.split('//')[0].strip()
        if not line: continue
        if re.match(r'subckt\b',line,re.I): inside=True;result.append(line)
        elif re.match(r'ends\b',line,re.I): inside=False;result.append(line)
        elif re.match(r'\S+\s+\([^)]*\)\s+\S+',line): result.append(line)
        elif line.startswith('parameters') and inside: result.append(line)
        elif re.match(r'(simulator|global|parameters|include|save|simulatorOptions|\w+\s+(options|info|dc|ac|tran|noise))\b',line):
            # Top-level model/analysis/options are supplied below; preserve original as evidence.
            if inside or line.startswith('include'): raise ValueError('Unexpected nested/include construct in native body; review required')
        else: raise ValueError('Unsupported native netlist line; cannot silently discard: '+line[:150])
    if inside: raise ValueError('Unterminated subckt')
    if not result: raise ValueError('Empty native netlist')
    return '\n'.join(result)+'\n'

def deck(job,body,cfg):
    s='simulator lang=spectre\nglobal 0\nparameters '+' '.join(k+'='+str(v) for k,v in job['params'].items())+'\n'
    s+='include '+quote(cfg['model'])+' section='+job['corner']+'\n'+body
    s+='p1bOptions options reltol=1e-5 vabstol=1e-7 iabstol=1e-13 temp='+str(job['temp'])+' tnom=27 scale=1 scalem=1\n'
    s+='saveOptions options save=allpub currents=all\ndcOp dc\ndcOpInfo info what=oppoint where=rawfile\n'
    a=job['analysis']
    if a=='res_dc': s+='dc dc param=VTEST start=0 stop=0.1 step=0.001\n'
    if a=='swing': s+='dc dc param=VCM start=0 stop=1.8 step=0.01\n'
    if a=='ac': s+='ac ac start=1 stop=1G dec=120\n'
    if a=='step': s+='tran tran stop=5u maxstep=0.5n errpreset=conservative\n'
    if a=='rc_step': s+='tran tran stop=10n maxstep=0.5p errpreset=conservative\n'
    if a=='noise': s+='noise (VOUT VSS) noise iprobe=VINP start=10 stop=1Meg dec=100\n'
    return s

def export_script(job,out,mapping):
    s='openResults('+quote(out/'psf')+')\n'
    s+='''procedure(p1bDump(signal result file)
      let((wave xv yv f n)
        wave=getData(signal ?result result)
        unless(wave error("Required signal missing: %s %L" signal result))
        unless(drIsWaveform(wave) error("Expected waveform: %s" signal))
        xv=drGetWaveformXVec(wave) yv=drGetWaveformYVec(wave)
        f=outfile(file) fprintf(f "x,real,imag\\n")
        n=drVectorLength(xv)
        for(i 0 n-1 fprintf(f "%.16g,%.16g,%.16g\\n" drGetElem(xv i) real(drGetElem(yv i)) imag(drGetElem(yv i))))
        close(f)))
'''
    a=job['analysis']
    result={'step':'tran','rc_step':'tran','res_dc':'dc','swing':'dc','noise':'noise','op':'dcOp','ac':'ac'}[a]
    signals={'res_dc':['TEST','VTEST:p'],'rc_step':['VIN','VOUT'],'ac':['VOUT','VINP','VINN','VSS','VDD'],
             'step':['VINP','VOUT'],'swing':['VINP','VOUT'],'noise':['out','in'],'op':[]}[a]
    if job['cell']=='p1b_tb_mim': signals=['TEST','VTEST:p']
    for sig in signals:
        if ':' not in sig and sig not in ['in','out']: actual=mapping.get(sig,sig)
        else: actual=sig
        s+='p1bDump('+quote(actual)+" '"+result+' '+quote(out/(sig.replace(':','_')+'.csv'))+')\n'
    # Keep full raw operating point info; portable scalar export for common nodes and device metrics.
    if job['cell'].startswith('p1b_tb_') and job['cell'] not in ['p1b_tb_res','p1b_tb_mim','p1b_tb_rc']:
        s+='p1bF=outfile('+quote(out/'op.csv')+')\nfprintf(p1bF "name,value\\n")\n'
        for node in ['VOUT','VINP','VSS','VBP','VDD']:
            s+='p1bV=getData('+quote(mapping.get(node,node))+' ?result \'dcOp)\nunless(numberp(p1bV) error("Missing DC scalar"))\nfprintf(p1bF '+quote(node+',%.16g\n')+' p1bV)\n'
        s+='p1bV=getData("VDD:p" ?result \'dcOp)\nunless(numberp(p1bV) error("Missing supply current"))\nfprintf(p1bF "ivdd,%.16g\\n" p1bV)\nclose(p1bF)\n'
        s+='p1bF=outfile('+quote(out/'op_devices.csv')+')\nfprintf(p1bF "device,ids,gm,gds,vds,vdsat\\n")\n'
        for dev in ['M1','M2','M3A','M3B','M4A','M4B','M5','M6','M7A','M7B','M8','M9','M10']:
            for attr in ['ids','gm','gds','vds','vdsat']:
                s+='p1b_'+attr+'=pv('+quote('XOTA.'+dev)+' '+quote(attr)+' ?result \'dcOpInfo)\nunless(numberp(p1b_'+attr+') error("Missing device OP '+dev+'.'+attr+'"))\n'
            s+='fprintf(p1bF '+quote(dev+',%.16g,%.16g,%.16g,%.16g,%.16g\n')+' p1b_ids p1b_gm p1b_gds p1b_vds p1b_vdsat)\n'
        s+='close(p1bF)\n'
    s+='p1bF=outfile('+quote(out/'export_complete.txt')+')\nfprintf(p1bF "COMPLETE\\n")\nclose(p1bF)\nexit()\n'
    return s

def log_audit(text,code):
    completion=bool(re.search(r'Spectre completes with\s+0 errors',text,re.I))
    warnings=re.findall(r'WARNING[^\n]*(?:\n[^\n]*)?',text)
    return dict(status='PASS' if code==0 and completion else 'FAIL',exit_code=code,normal_completion=completion,warnings=warnings)

def prerequisites(job):
    required=[]
    if job['group'] in ['nominal','pvt','extra']: required+=['res_dc','mim_ac','rc_step']
    if job['group'] in ['pvt','extra']: required+=['P01_op','P01_ac','P01_loop','P01_step']
    for ident in required:
        attempts=sorted((ROOT/'runs'/ident).glob('*/status.json'))
        if not attempts: raise ValueError('Prerequisite NOT_RUN: '+ident)
        state=json.loads(attempts[-1].read_text())
        if state['status']!='PASS' or state['performance_status']!='PASS' or state.get('package_sha256')!=sha(ROOT/'package_manifest.json'):
            raise ValueError('Prerequisite not qualified for this package: '+ident+' (latest retained attempt '+attempts[-1].parent.name+')')

def run_one(job,cfg):
    out=ROOT/'runs'/job['id']/stamp();out.mkdir(parents=True)
    state=dict(job=job,status='NOT_RUN',performance_status='NOT_RUN',package_sha256=sha(ROOT/'package_manifest.json'),site=cfg)
    write(out/'status.json',state)
    try:
        for key in ['ocean','spectre']:
            if not os.access(cfg[key],os.X_OK): raise OSError(key+' executable unavailable: '+cfg[key])
        if not Path(cfg['model']).is_file(): raise OSError('Model file unavailable')
        invoke([cfg['spectre'],'-W'],out/'spectre_version.txt',cfg['workdir'])
        script=out/'netlist.ocn';script.write_text(netlist_script(job,out,cfg))
        code=invoke([cfg['ocean'],'-nograph'],out/'ocean_netlist.log',cfg['workdir'],script)
        if code or not (out/'netlist_return.txt').exists(): raise OSError('Native netlisting failed; see ocean_netlist.log')
        raw=native_netlist_path(out).read_text()
        (out/'native_netlist.scs').write_text(raw)
        audited=check(raw,read('design.json'),job['cell'],job['params'])
        write(out/'netlist_audit.json',audited)
        body=netlist_body(raw)
        target=out/'input.scs';target.write_text(deck(job,body,cfg))
        state['native_netlist_sha256']=sha(out/'native_netlist.scs');state['input_sha256']=sha(target)
        state['model_entry_sha256']=sha(Path(cfg['model']))
        code=invoke([cfg['spectre'],str(target),'-format','psfbin','-raw',str(out/'psf'),'+log',str(out/'spectre.out')],out/'spectre_console.log',out)
        text=(out/'spectre.out').read_text(errors='replace') if (out/'spectre.out').exists() else ''
        audited_log=log_audit(text,code);write(out/'log_audit.json',audited_log)
        if audited_log['status']!='PASS': raise RuntimeError('Spectre did not complete normally')
        script=out/'export.ocn';script.write_text(export_script(job,out,audited['top_net_map']))
        code=invoke([cfg['ocean'],'-nograph'],out/'ocean_export.log',cfg['workdir'],script)
        if code or not (out/'export_complete.txt').exists(): raise RuntimeError('Simulation finished, data export failed; raw PSF retained')
        from analyze import analyze
        metrics=analyze(out,job);write(out/'metrics.json',metrics)
        state.update(status='PASS',performance_status=metrics['status'])
    except OSError as e: state.update(status='ENV_BLOCKED',error=str(e))
    except Exception as e: state.update(status='FAIL',error=str(e))
    write(out/'status.json',state)
    print(job['id'],state['status'],state['performance_status'],state.get('error',''),str(out),flush=True)
    return state

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command')
    sub.add_parser('prepare');sub.add_parser('list');sub.add_parser('collect');sub.add_parser('summary')
    r=sub.add_parser('run');r.add_argument('--group',choices=['passives','nominal','pvt','extra','all'],default='passives');r.add_argument('--job');r.add_argument('--retry',action='store_true')
    args=p.parse_args()
    if not args.command: p.error('Choose prepare, list, run, summary or collect')
    verify()
    jobs=read('jobs.json');cfg=config()
    if args.command=='prepare':
        if not (ROOT/'site.json').exists(): write(ROOT/'site.json',cfg)
        print('In the already-open Virtuoso CIW, paste this single line:')
        print('p1bRoot='+quote(ROOT)+' load(strcat(p1bRoot "/create.il"))')
        print('After P1B_ALL_CREATED, return here and run: python3 run.py run --group passives')
    elif args.command=='list':
        for j in jobs: print(j['id'],j['group'],j['cell'],j['corner'],j['temp'])
    elif args.command=='run':
        if not (ROOT/'created.txt').exists(): sys.exit('Run prepare and the CIW load first. No native views have been confirmed.')
        selected=[j for j in jobs if j['id']==args.job] if args.job else [j for j in jobs if args.group=='all' or j['group']==args.group]
        if not selected: sys.exit('No matching job')
        for j in selected:
            previous=list((ROOT/'runs'/j['id']).glob('*/status.json'))
            if previous and not args.retry:
                print(j['id'],'ALREADY_ATTEMPTED (use --retry for a new retained attempt)');continue
            try: prerequisites(j)
            except ValueError as e: sys.exit(str(e))
            state=run_one(j,cfg)
            if state['status']!='PASS': sys.exit(1)
            if j['group'] in ['passives','nominal'] and state['performance_status']=='FAIL':
                sys.exit('Measurement criteria failed. Results preserved; review before the next stage.')
    elif args.command=='summary':
        rows=[]
        for j in jobs:
            results=list((ROOT/'runs'/j['id']).glob('*/status.json'))
            if not results:
                print(j['id'],'NOT_RUN');rows.append(dict(job=j['id'],attempt='',status='NOT_RUN',performance_status='NOT_RUN',metrics=''))
            for result in sorted(results):
                s=json.loads(result.read_text());print(j['id'],result.parent.name,s['status'],s['performance_status'])
                rows.append(dict(job=j['id'],attempt=result.parent.name,status=s['status'],performance_status=s['performance_status'],metrics=str(result.parent/'metrics.json')))
        with (ROOT/'attempts.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=['job','attempt','status','performance_status','metrics']);w.writeheader();w.writerows(rows)
    elif args.command=='collect':
        dest=ROOT/('project1_basic_report_'+stamp()+'.zip')
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
            names=['package_manifest.json','site.json','created.txt','create_status.txt','cdf_values.tsv','local_status.json','attempts.csv',
                   'runtime_patch.json','patch_backups/v1_0_4p1/run.py','patch_backups/v1_0_4p1/package_manifest.json']
            for name in names:
                if (ROOT/name).is_file(): z.write(ROOT/name,name)
            for f in (ROOT/'runs').rglob('*'):
                if f.is_file() and not f.is_symlink():
                    # native work files are redundant; include original netlist, input, logs, PSF, all CSV and status.
                    if 'native' not in f.relative_to(ROOT).parts: z.write(f,f.relative_to(ROOT))
        print(dest)

if __name__=='__main__': main()
