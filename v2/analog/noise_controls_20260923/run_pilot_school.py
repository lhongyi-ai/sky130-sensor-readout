from completion_summary import parse_completion, execution_completed
"""Explicit serial pilot launcher; reads ignored site.private.json. No batch expansion."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,shlex,subprocess,time,uuid
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 prep=ROOT/'prepared/pilot_r1';mp=prep/'manifest.json';manifest=json.loads(mp.read_text());jobs=[j for j in manifest['jobs'] if j['id']==a.job];assert len(jobs)==1;j=jobs[0]
 assert manifest['profile']=='pilot' and j.get('n_samples',64)==64
 source=prep/j['input_file'];assert sha(source)==j['input_sha256']
 if not a.execute:print('NOT_RUN: require allocated slot and explicit --execute');return
 site=json.loads((ROOT/'site.private.json').read_text());host=site['host'];stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
 run=ROOT/'runs'/j['id']/stamp;run.mkdir(parents=True);remote=site['remote_base']+'/'+j['id']+'/'+stamp
 def ssh(cmd,timeout=45):return subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',host,cmd],capture_output=True,text=True,timeout=timeout)
 r=ssh('mkdir -p '+shlex.quote(remote));assert r.returncode==0,r.stderr
 (run/'input.scs').write_bytes(source.read_bytes())
 wrap=(REPO/'v2/cadence/linuxlab_20260923/run_si.sh').read_text().replace('exec si -batch -cdslib "$USERDIR/cds.lib" -command nl','exec spectre input.scs +log spectre.out -format psfascii -raw raw +lqtimeout 60')
 (run/'run_school.sh').write_text(wrap)
 for name in ['input.scs','run_school.sh']:
  r=subprocess.run(['scp','-o','BatchMode=yes',str(run/name),host+':'+remote+'/'+name],capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
 hash_result=ssh('sha256sum '+shlex.quote(manifest['model_path']));assert hash_result.returncode==0
 s=dict(job=j,status='RUNNING',qualification='NOT_EVALUATED',input_sha256=j['input_sha256'],prepared_manifest_sha256=sha(mp),model_entry_sha256=hash_result.stdout.split()[0],model_section=manifest['model_section'],theory=manifest['theory'],remote_run=remote)
 (run/'status.json').write_text(json.dumps(s,indent=2)+'\n');t=time.monotonic()
 r=ssh('timeout --signal=TERM --kill-after=10s 300s bash '+shlex.quote(remote+'/run_school.sh')+' '+shlex.quote(remote)+' </dev/null >'+shlex.quote(remote+'/console.log')+' 2>&1',timeout=340)
 s['exit_code']=r.returncode;s['wall_seconds']=time.monotonic()-t
 (run/'ssh_result.json').write_text(json.dumps({'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr},indent=2)+'\n')
 for name in ['spectre.out','console.log','raw']:
  cp=subprocess.run(['scp','-r','-o','BatchMode=yes',host+':'+remote+'/'+name,str(run/name)],capture_output=True,text=True,timeout=90)
  if cp.returncode!=0:s.setdefault('download_errors',{})[name]=cp.stderr
 log=(run/'spectre.out').read_text(errors='replace') if (run/'spectre.out').exists() else ''
 end=parse_completion(log)
 s['summary_counts']=end;s['status']='PASS' if execution_completed(r.returncode,log) else 'FAIL'
 s['warnings']=[l for l in log.splitlines() if re.match(r'\s*(?:WARNING\b|Warning from\b)',l,re.I)]
 s['warning_review']='REQUIRED' if s['warnings'] else 'NO_WARNING_LINES'
 s['tool_version_lines']=[l for l in log.splitlines() if l.startswith('Version ')]
 s['cpu_elapsed_lines']=[l for l in log.splitlines() if 'Time used: CPU' in l or 'Total time required for' in l]
 s['artifact_hashes']={str(f.relative_to(run)):sha(f) for f in run.rglob('*') if f.is_file() and f.name!='status.json'}
 (run/'status.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps({'run':str(run),'status':s['status'],'wall_seconds':s['wall_seconds'],'summary_counts':s['summary_counts'],'warnings':s['warnings']}))
if __name__=='__main__':main()
