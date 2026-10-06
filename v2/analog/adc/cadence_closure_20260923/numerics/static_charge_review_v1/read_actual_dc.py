#!/usr/bin/env python3
"""Read actual scalar DC PSFASCII schema and values; no invented charge fields."""
from pathlib import Path
import argparse,hashlib,json,math,re
P='XTEST.msky130_fd_pr__pfet_01v8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read_dc(path):
 section='header';header={};schema={};aliases={};axis=None;group=None;prop=False;sweep_prop=False;row=None;rows=[]
 def finish():
  if row is None:return
  if set(row)!={axis,*schema}:raise ValueError('IncompleteDCrow; missing:'+str({axis,*schema}-set(row)))
  if not all(math.isfinite(x) for x in row.values()):raise ValueError('NonfiniteDCvalue')
  rows.append(row.copy())
 for line in path.read_text().splitlines():
  l=line.strip()
  if l in ['TYPE','SWEEP','TRACE','VALUE']:
   section=l
   if l=='VALUE' and (axis is None or not schema):raise ValueError('Noactualaxis/schema')
   continue
  if section=='header':
   m=re.fullmatch(r'"([^"]+)"\s+"([^"]*)"',l)
   if m:header[m[1]]=m[2]
   else:
    m=re.fullmatch(r'\"([^\"]+)\"\s+([-+.0-9eE]+)',l)
    if m:header[m[1]]=float(m[2])
   continue
  if section=='SWEEP':
   if sweep_prop:
    if l==')':sweep_prop=False
    continue
   m=re.match(r'^"([^"]+)"\s+',l)
   if m:
    if axis is not None:raise ValueError('MultipleDCsweepaxesunsupported')
    axis=m[1];sweep_prop=l.endswith('PROP(')
   continue
  if section=='TRACE':
   if prop:
    if l==')':prop=False
    continue
   m=re.fullmatch(r'"([^"]+)" GROUP (\d+)',l)
   if m:
    if m[2]!='1':raise ValueError('NonscalarGROUPunsupported')
    group=m[1];continue
   m=re.match(r'^"([^"]+)"\s+"([^"]+)"',l)
   if m:
    if m[1] in schema:raise ValueError('Duplicateactualsignal')
    schema[m[1]]=m[2];prop=l.endswith('PROP(')
    if group is not None:aliases[group]=m[1];group=None
   continue
  if section=='VALUE':
   m=re.fullmatch(r'"([^"]+)"\s+([-+.0-9eE]+)',l)
   if not m:
    if l not in ['','END']:raise ValueError('UnexpectedactualDCvalueencoding:'+l[:160])
    continue
   n,x=m[1],float(m[2]);n=aliases.get(n,n)
   if n==axis:finish();row={axis:x}
   else:
    if row is None:raise ValueError('Valuebeforeaxis')
    if n not in schema:raise ValueError('Undeclaredactualsignal:'+n)
    if n in row:raise ValueError('DuplicatedactualsignalwithinDCrow:'+n)
    row[n]=x
 finish()
 if len(rows)<2:raise ValueError('InsufficientactualDCrows')
 diffs=[b[axis]-a[axis] for a,b in zip(rows,rows[1:])]
 if not(all(d>0 for d in diffs) or all(d<0 for d in diffs)):raise ValueError('NonmonotonicDCaxis; preserveandinvestigate')
 return header,axis,schema,rows

def inspect(run):
 m=json.loads((run/'package_manifest.json').read_text());profile=(run/'profile.txt').read_text().strip();expected=m['profiles'][profile]
 if sha(run/'input.scs')!=expected['sha256']:raise ValueError('Frozeninputhashmismatch')
 result={'status':'DC_OUTPUT_OBSERVABILITY_REVIEW_ONLY','profile':profile,'run':str(run),'input_sha256':sha(run/'input.scs'),'exit_code':int((run/'exit_code.txt').read_text()),'sweeps':{},'complete_ADC':False,'full_ADC_accuracy_pass':False}
 for name,sweep in expected['sweeps'].items():
  paths=[p for p in (run/'input.raw').glob(name+'.*') if p.is_file()]
  if len(paths)!=1:raise ValueError('Expecteduniqueactualrawfor '+name+':'+str(paths))
  header,axis,schema,rows=read_dc(paths[0]);mapping={};missing=[]
  if not {'D','G','SB'}.issubset(schema):raise ValueError('Missingexternalbiasnode')
  for f in ['int_b','dbnode','sbnode']:
   if len([n for n in [P+':'+f,P+'.'+f] if n in schema])!=1:raise ValueError('Missingorambiguousinternalbody:'+f)
  for f in m['documented_op_fields']:
   found=[n for n in [P+':'+f,P+'.'+f] if n in schema]
   if len(found)!=1:missing.append(f)
   else:mapping[f]=found[0]
  if set(missing)-{'ig','is','ib'}:raise ValueError('Requiredcharge/C/biasOPmissing:'+str(missing))
  values=set(r[mapping['reversed']] for r in rows)
  if not values<={0.,1.}:raise ValueError('Unexpectedactualreversedvalues:'+str(values))
  expected_points=sweep['expected_points'];measured=[r['D']-r['SB'] for r in rows]
  result['sweeps'][name]={'raw_path':str(paths[0]),'sha256':sha(paths[0]),'actual_header':header,'actual_axis':axis,'actual_schema':schema,'OP_aliases':mapping,'missing_requested_OP_fields':missing,'missing_OP_handling':'Notfilledorsynthesized; actuald/g/s/bterminalcurrents are separate saved observables, not replacementclaimedfor missingOPaliases.','actual_points':len(rows),'expected_points':expected_points,'point_count_matches':len(rows)==expected_points,'actual_axis_range':[rows[0][axis],rows[-1][axis]],'measured_D_minus_SB_range_V':[measured[0],measured[-1]],'requested_range_V':[sweep['start_V'],sweep['stop_V']],'reversed_values':sorted(values),'q_ranges_C':{f:[min(r[mapping[f]] for r in rows),max(r[mapping[f]] for r in rows)] for f in ['qg','qd','qs','qb','qjd','qjs','qgi','qdi','qsi','qbi']},'mode_edges':[{'before_axis':a[axis],'after_axis':b[axis],'before_reversed':a[mapping['reversed']],'after_reversed':b[mapping['reversed']]} for a,b in zip(rows,rows[1:]) if a[mapping['reversed']]!=b[mapping['reversed']]],'analysis_limit':'Schema/finitevaluescheckedonly; no charge-conservation,partialderivative equivalence or physicalcontinuity conclusion.'}
 before=json.loads((run/'model_metadata_before.json').read_text());after=json.loads((run/'model_metadata_after.json').read_text());result['model_hashes_before_after_equal']=before==after;result['model_hash_comparison_exit']=int((run/'model_hash_comparison_exit.txt').read_text())
 log=(run/'spectre.out').read_text(errors='replace');result['log_completion']=re.findall(r'spectre completes with [^\n]+',log)
 return result
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('run',type=Path);a.add_argument('output',type=Path);args=a.parse_args();r=inspect(args.run);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
