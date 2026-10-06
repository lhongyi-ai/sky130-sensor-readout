from completion_summary import parse_completion, execution_completed
"""Future school-side serial runner. Explicit --execute is required; no SSH or GUI."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,re,shutil,subprocess,time,uuid

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--job',required=True);p.add_argument('--spectre',default='spectre');p.add_argument('--results',type=Path,required=True);p.add_argument('--timeout',type=float,default=300);p.add_argument('--execute',action='store_true');a=p.parse_args()
 mpath=a.prepared/'manifest.json';m=json.loads(mpath.read_text());js=[j for j in m['jobs'] if j['id']==a.job];assert len(js)==1
 j=js[0];source=a.prepared/j['input_file'];assert sha(source)==j['input_sha256'],'Prepared input changed'
 if not a.execute:print(json.dumps({'status':'NOT_RUN','reason':'Add --execute only after the parent allocates the single simulation slot','job':j['id']}));return
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
 run=a.results.resolve()/j['id']/stamp;run.mkdir(parents=True,exist_ok=False);shutil.copy2(source,run/'input.scs')
 s={'job':j,'status':'NOT_RUN','qualification':'NOT_EVALUATED','input_sha256':j['input_sha256'],'prepared_manifest_sha256':sha(mpath),'model_section':m['model_section'],'theory':m['theory']}
 model=Path(m['model_path']);exe=shutil.which(a.spectre)
 if exe is None or ((j['kind'].startswith('tg') or j['kind']=='mim_ac') and not model.is_file()):
  s.update(status='ENV_BLOCKED',reason='Executable or required model entry unavailable')
 else:
  s['spectre_executable']=exe
  if model.is_file():s['model_entry_sha256']=sha(model)
  v=subprocess.run([exe,'-W'],capture_output=True,text=True,timeout=20);(run/'tool_version.txt').write_text(v.stdout+v.stderr)
  cmd=[exe,'input.scs','+log','spectre.out','-format','psfascii','-raw','raw','+lqtimeout','60'];s.update(status='RUNNING',command=cmd)
  (run/'status.json').write_text(json.dumps(s,indent=2)+'\n');t=time.monotonic()
  try:
   with (run/'console.log').open('w') as f:r=subprocess.run(cmd,cwd=run,stdout=f,stderr=subprocess.STDOUT,timeout=a.timeout)
   s['exit_code']=r.returncode
   log=(run/'spectre.out').read_text(errors='replace') if (run/'spectre.out').exists() else ''
   end=parse_completion(log)
   s['summary_counts']=end
   s['warnings']=[l for l in log.splitlines() if re.match(r'\s*(?:WARNING\b|Warning from\b)',l,re.I)]
   s['status']='PASS' if execution_completed(r.returncode,log) else 'FAIL'
   s['warning_review']='REQUIRED' if s['warnings'] else 'NO_WARNING_LINES'
  except subprocess.TimeoutExpired:s.update(status='FAIL',reason='TIMEOUT',exit_code=None)
  s['wall_seconds']=time.monotonic()-t
 s['qualification']='NOT_EVALUATED';s['completed_utc']=datetime.now(timezone.utc).isoformat()
 s['artifact_hashes']={str(f.relative_to(run)):sha(f) for f in run.rglob('*') if f.is_file() and f.name!='status.json'}
 (run/'status.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps({'run':str(run),'execution_status':s['status'],'qualification':s['qualification']}))
if __name__=='__main__':main()
