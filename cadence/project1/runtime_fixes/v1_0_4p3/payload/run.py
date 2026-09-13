#!/usr/bin/env python3
"""Linux entry point. Standard library only. Sequential, immutable attempts."""
import argparse
import csv
import datetime
import hashlib
import json
import math
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

OP_DEVICES=['M1','M2','M3A','M3B','M4A','M4B','M5','M6','M7A','M7B','M8','M9','M10']
OP_PMOS={'M3A','M3B','M4A','M4B','M7A','M7B','M8','M9'}

def op_leaf(dev):
    kind='pfet' if dev in OP_PMOS else 'nfet'
    return 'XOTA.'+dev+'.msky130_fd_pr__'+kind+'_01v8'

def export_script(job,out,mapping):
    # One protected operation: an error cannot fall through the interactive
    # input stream to write a misleading completion marker.
    s='procedure(p1bExportAll()\n'
    s+='unless(openResults('+quote(out/'psf')+') error("Cannot open PSF results"))\n'
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
        s+='unless(selectResult(\'dcOpInfo) error("Cannot select device operating point result"))\n'
        s+='p1bNames=outputs()\np1bNF=outfile('+quote(out/'op_available_names.txt')+')\nfprintf(p1bNF "%L\\n" p1bNames)\nclose(p1bNF)\n'
        s+='p1bMF=outfile('+quote(out/'op_instance_map.csv')+')\nfprintf(p1bMF "device,signal\\n")\n'
        s+='p1bF=outfile('+quote(out/'op_devices.csv')+')\nfprintf(p1bF "device,ids,gm,gds,vds,vdsat\\n")\n'
        for dev in OP_DEVICES:
            raw=op_leaf(dev); schematic='/'+raw.replace('.','/')
            s+='p1bName=cond((member('+quote(raw)+' p1bNames) '+quote(raw)+')\n'
            s+=' (member('+quote(schematic)+' p1bNames) '+quote(schematic)+')\n'
            s+=' (t error("Expected internal MOS missing: '+raw+'; see op_available_names.txt")))\n'
            s+='p1bDevice=getData(p1bName)\nunless(p1bDevice error("Missing device structure: %s" p1bName))\n'
            for attr in ['ids','gm','gds','vds','vdsat']:
                s+='p1b_'+attr+'=p1bDevice->'+attr+'\nunless(numberp(p1b_'+attr+') error("Missing device OP '+dev+'.'+attr+'"))\n'
            s+='fprintf(p1bF '+quote(dev+',%.16g,%.16g,%.16g,%.16g,%.16g\n')+' p1b_ids p1b_gm p1b_gds p1b_vds p1b_vdsat)\n'
            s+='fprintf(p1bMF '+quote(dev+',%s\n')+' p1bName)\n'
        s+='close(p1bF)\nclose(p1bMF)\n'
    s+='p1bF=outfile('+quote(out/'export_complete.txt')+')\nfprintf(p1bF "COMPLETE\\n")\nclose(p1bF)\nt)\n'
    s+='p1bExportResult=errset(p1bExportAll() t)\nif(p1bExportResult then exit(0) else exit(1))\n'
    return s

def validate_export(out,job,code):
    log=(out/'ocean_export.log').read_text(errors='replace')
    if code or re.search(r'\*Error\*|(?m:^ERROR\s*\()',log):
        raise RuntimeError('OCEAN export failed; see ocean_export.log and op_available_names.txt')
    if not (out/'export_complete.txt').is_file() or (out/'export_complete.txt').read_text().strip()!='COMPLETE':
        raise RuntimeError('OCEAN export completion missing; raw PSF retained')
    if job['group']=='passives': return
    with (out/'op_devices.csv').open() as f: rows=list(csv.DictReader(f))
    if len(rows)!=13 or {r['device'] for r in rows}!=set(OP_DEVICES):
        raise RuntimeError('Device OP export incomplete: expected 13 devices, found '+str(len(rows)))
    for r in rows:
        for key in ['ids','gm','gds','vds','vdsat']:
            if not math.isfinite(float(r[key])): raise RuntimeError('Nonfinite device OP: '+r['device']+'.'+key)
    with (out/'op_instance_map.csv').open() as f: names=list(csv.DictReader(f))
    if len(names)!=13 or {r['device'] for r in names}!=set(OP_DEVICES) or any(r['signal'] not in (op_leaf(r['device']),'/'+op_leaf(r['device']).replace('.','/')) for r in names):
        raise RuntimeError('Device OP source mapping incomplete or unexpected')
    with (out/'op.csv').open() as f: scalars=list(csv.DictReader(f))
    if len(scalars)!=6 or {r['name'] for r in scalars}!={'VOUT','VINP','VSS','VBP','VDD','ivdd'} or any(not math.isfinite(float(r['value'])) for r in scalars):
        raise RuntimeError('Scalar operating point export incomplete or nonfinite')

def log_audit(text,code):
    completion=bool(re.search(r'Spectre completes with\s+0 errors',text,re.I))
    warnings=re.findall(r'WARNING[^\n]*(?:\n[^\n]*)?',text)
    return dict(status='PASS' if code==0 and completion else 'FAIL',exit_code=code,normal_completion=completion,warnings=warnings)

def prerequisites(job):
    required=[]
    if job['group'] in ['nominal','pvt','extra']:
        from passive_review import review_passives, same_evidence
        reviews=sorted((ROOT/'runs/passive_reviews').glob('*/review.json'))
        if not reviews: raise ValueError('Run recheck-passives first; original results will be preserved')
        saved=json.loads(reviews[-1].read_text())
        current=review_passives(ROOT,config(),deck,netlist_body,log_audit)
        if not same_evidence(saved,current):
            raise ValueError('Passive review failed or evidence changed; run recheck-passives and review its result')
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
        state['simulation_status']='PASS';state['export_status']='NOT_RUN'
        script=out/'export.ocn';script.write_text(export_script(job,out,audited['top_net_map']))
        code=invoke([cfg['ocean'],'-nograph'],out/'ocean_export.log',cfg['workdir'],script)
        state['export_status']='FAIL'
        validate_export(out,job,code)
        state['export_status']='PASS'
        from analyze import analyze
        metrics=analyze(out,job);write(out/'metrics.json',metrics)
        state.update(status='PASS',performance_status=metrics['status'])
    except OSError as e: state.update(status='ENV_BLOCKED',error=str(e))
    except Exception as e: state.update(status='FAIL',error=str(e))
    write(out/'status.json',state)
    print(job['id'],state['status'],state['performance_status'],state.get('error',''),str(out),flush=True)
    return state

def resume_export(job,attempt,cfg):
    if job['group']=='passives' or not re.fullmatch(r'\d{8}T\d{6}Z_[0-9a-f]{8}',attempt):
        raise ValueError('Resume requires an OTA job and an exact retained attempt name')
    source=ROOT/'runs'/job['id']/attempt
    previous=json.loads((source/'status.json').read_text())
    compatible={'3502851b9bacef25d0c2e9f21aee3aef4de3baf5a88e9e7476bde57417e54933',sha(ROOT/'package_manifest.json')}
    if previous['job']!=job or previous['package_sha256'] not in compatible:
        raise ValueError('Source job or package differs; cannot reuse PSF')
    if any(previous['site'].get(k)!=cfg.get(k) for k in ['ocean','spectre','model','workdir']):
        raise ValueError('Site differs from the source simulation')
    if sha(Path(cfg['model']))!=previous['model_entry_sha256']:
        raise ValueError('Model entry changed; cannot reuse PSF')
    raw=(source/'native_netlist.scs').read_text()
    audited=check(raw,read('design.json'),job['cell'],job['params'])
    selection=json.loads((source/'native_selection.json').read_text())
    if sha(source/'native_netlist.scs')!=previous['native_netlist_sha256'] or selection['selected_body_sha256']!=previous['native_netlist_sha256'] or sha(source/'native_input.scs')!=selection['returned_input_sha256']:
        raise ValueError('Source native netlist evidence changed')
    if sha(source/'input.scs')!=previous['input_sha256'] or (source/'input.scs').read_text()!=deck(job,netlist_body(raw),cfg):
        raise ValueError('Source simulation input changed')
    logged=json.loads((source/'log_audit.json').read_text())
    if log_audit((source/'spectre.out').read_text(),logged['exit_code'])['status']!='PASS':
        raise ValueError('Source Spectre simulation did not complete normally')
    for name in ['logFile','dcOp.dc','dcOpInfo.info']:
        if not (source/'psf'/name).is_file(): raise ValueError('Missing source PSF file: '+name)
    if any(p.is_symlink() for p in source.rglob('*')): raise ValueError('Source attempt contains redirected files')
    out=ROOT/'runs'/job['id']/stamp();out.mkdir(parents=True)
    state=dict(job=job,status='NOT_RUN',performance_status='NOT_RUN',package_sha256=sha(ROOT/'package_manifest.json'),site=cfg,
               simulation_status='PASS',simulation_origin='RETAINED_SPECTRE_RESULTS',recovered_from_attempt=attempt,
               export_status='NOT_RUN',native_netlist_sha256=previous['native_netlist_sha256'],
               input_sha256=previous['input_sha256'],model_entry_sha256=previous['model_entry_sha256'])
    write(out/'status.json',state)
    try:
        names=['native_input.scs','native_netlist.scs','native_selection.json','netlist_audit.json','input.scs',
               'spectre.out','log_audit.json','spectre_version.txt']
        proof={n:sha(source/n) for n in names+['status.json','ocean_export.log','op_devices.csv'] if (source/n).is_file()}
        proof.update({p.relative_to(source).as_posix():sha(p) for p in (source/'psf').rglob('*') if p.is_file()})
        write(out/'recovery_source.json',dict(source_attempt=attempt,source_status=previous,source_files_sha256=proof,
             new_spectre_execution=False))
        for name in names: shutil.copy2(str(source/name),str(out/name))
        shutil.copytree(str(source/'psf'),str(out/'psf'))
        script=out/'export.ocn';script.write_text(export_script(job,out,audited['top_net_map']))
        code=invoke([cfg['ocean'],'-nograph'],out/'ocean_export.log',cfg['workdir'],script)
        state['export_status']='FAIL';validate_export(out,job,code);state['export_status']='PASS'
        from analyze import analyze
        metrics=analyze(out,job);write(out/'metrics.json',metrics)
        state.update(status='PASS',performance_status=metrics['status'])
    except OSError as error: state.update(status='ENV_BLOCKED',error=str(error))
    except Exception as error: state.update(status='FAIL',error=str(error))
    write(out/'status.json',state)
    print(job['id'],state['status'],state['performance_status'],'RESUMED_EXPORT',state.get('error',''),str(out),flush=True)
    return state

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command')
    sub.add_parser('prepare');sub.add_parser('list');sub.add_parser('collect');sub.add_parser('summary');sub.add_parser('recheck-passives')
    r=sub.add_parser('run');r.add_argument('--group',choices=['passives','nominal','pvt','extra','all'],default='passives');r.add_argument('--job');r.add_argument('--retry',action='store_true')
    r=sub.add_parser('resume-export');r.add_argument('--job',required=True);r.add_argument('--attempt',required=True)
    args=p.parse_args()
    if not args.command: p.error('Choose prepare, list, run, summary, recheck-passives or collect')
    verify()
    jobs=read('jobs.json');cfg=config()
    if args.command=='resume-export':
        job=next((j for j in jobs if j['id']==args.job),None)
        if job is None: sys.exit('Unknown job')
        try:
            prerequisites(job)
            state=resume_export(job,args.attempt,cfg)
        except (OSError,ValueError) as error: sys.exit('P1_RESUME_EXPORT_STOPPED: '+str(error))
        if state['status']!='PASS' or state['performance_status']!='PASS': sys.exit(1)
    elif args.command=='recheck-passives':
        from passive_review import review_passives
        out=ROOT/'runs/passive_reviews'/stamp();out.mkdir(parents=True)
        try:
            reviewed=review_passives(ROOT,cfg,deck,netlist_body,log_audit)
        except Exception as error:
            write(out/'review.json',dict(status='FAIL',error=str(error),kind='REANALYSIS_STOPPED'))
            sys.exit('P1_PASSIVE_RECHECK_STOPPED: '+str(error)+' '+str(out))
        write(out/'review.json',reviewed)
        for ident,record in reviewed['records'].items():
            print(ident,'RECHECK',record['metrics']['status'],'original',record['source_status'],record['source_performance_status'])
        print('P1_PASSIVES_RECHECK_'+reviewed['status'],str(out))
        if reviewed['status']!='PASS': sys.exit(1)
    elif args.command=='prepare':
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
        reviews=sorted((ROOT/'runs/passive_reviews').glob('*/review.json'))
        if reviews:
            review=json.loads(reviews[-1].read_text())
            print('PASSIVE_RECHECK',review['status'],str(reviews[-1]))
            for ident,record in review.get('records',{}).items(): print(ident,'RECHECK',record['metrics']['status'])
    elif args.command=='collect':
        dest=ROOT/('project1_basic_report_'+stamp()+'.zip')
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
            names=['package_manifest.json','site.json','created.txt','create_status.txt','cdf_values.tsv','local_status.json','attempts.csv',
                   'runtime_patch.json','passive_criteria.md','patch_backups/v1_0_4p1/run.py','patch_backups/v1_0_4p1/package_manifest.json',
                   'patch_backups/v1_0_4p2/run.py','patch_backups/v1_0_4p2/analyze.py',
                   'patch_backups/v1_0_4p2/runtime_patch.json','patch_backups/v1_0_4p2/package_manifest.json',
                   'patch_backups/v1_0_4p3/run.py','patch_backups/v1_0_4p3/analyze.py',
                   'patch_backups/v1_0_4p3/passive_review.py','patch_backups/v1_0_4p3/runtime_patch.json',
                   'patch_backups/v1_0_4p3/package_manifest.json']
            for name in names:
                if (ROOT/name).is_file(): z.write(ROOT/name,name)
            for f in (ROOT/'runs').rglob('*'):
                if f.is_file() and not f.is_symlink():
                    # native work files are redundant; include original netlist, input, logs, PSF, all CSV and status.
                    if 'native' not in f.relative_to(ROOT).parts: z.write(f,f.relative_to(ROOT))
        print(dest)

if __name__=='__main__': main()
