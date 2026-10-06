#!/usr/bin/env python3
"""Read-only strict(actual 1e-7) -> finer(actual 1e-8) full short-domain audit.

Does not run EDA, modify inputs, omit switch edges, or relax the original gate.
Writes only a new requested output folder; an existing folder is refused.
"""
import argparse, hashlib, importlib.util, json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_review',HERE/'analyze.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
h=module.h
LIMIT=.05*.8/4096
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def end_marker(p):
    with p.open('rb') as f:f.seek(max(0,p.stat().st_size-256));return f.read().rstrip().endswith(b'END')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True,help='Returned nativeRC/lte1 strict run, actual reltol1e-7')
    parser.add_argument('--finer',type=Path,required=True,help='Returned finer run, expected actual reltol1e-8')
    parser.add_argument('--output',type=Path,required=True,help='New analysis folder; existing folder refused')
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Refusing to overwrite any existing report folder')
    args.output.mkdir(parents=True)
    profiles={};data={}
    for name,run in [('baseline',args.baseline),('finer',args.finer)]:
        run=run.resolve();raw=run/'amsdControl.raw/adc_closure_tran.tran.tran'
        m=json.loads((run/'manifest.json').read_text())
        info={**h.logs(run),'run':str(run),'manifest_sha256':sha(run/'manifest.json'),
          'manifest_files':m['files_sha256'],
          'all_manifest_hashes_match':all(sha(run/n)==v for n,v in m['files_sha256'].items()),
          'raw_sha256':sha(raw),'raw_END_present':end_marker(raw),'parse_error':None}
        try:
            data[name]=h.raw(run);info.update(data[name][2])
        except (ValueError,OverflowError) as e:
            info['parse_error']=str(e)
            # Keep malformed raw unchanged; do not remove/fill final row to manufacture completion.
        profiles[name]=info
    old=(args.baseline/'amsdControl.scs').read_text();new=(args.finer/'amsdControl.scs').read_text()
    expected=old.replace('reltol=1e-6 vabstol=1e-9 iabstol=1e-14','reltol=1e-7 vabstol=1e-10 iabstol=1e-15').replace('maxstep=1n','maxstep=0.5n')
    files=set(profiles['baseline']['manifest_files'])|set(profiles['finer']['manifest_files'])
    same_except_control={n:(args.baseline/n).is_file() and (args.finer/n).is_file() and (args.baseline/n).read_bytes()==(args.finer/n).read_bytes() for n in files if n!='amsdControl.scs'}
    checks={'all_input_hashes_match':all(p['all_manifest_hashes_match'] for p in profiles.values()),
      'only_planned_precision_profile_changed':old!=new and expected==new and all(same_except_control.values()),
      'two_PSFS_parse_without_salvage':len(data)==2,
      'both_end_markers':all(p['raw_END_present'] for p in profiles.values()),
      'both_actual_exit0':all(p['simulator_exit_code']==0 for p in profiles.values()),
      'no_unexplained_numerical_warnings':all(not p['warning_code_counts'] for p in profiles.values())}
    stats=None;domain=None;full=False
    if len(data)==2:
        a,b=data['baseline'],data['finer'];headers=[a[2]['actual_header'],b[2]['actual_header']]
        wanted={'reltol':(1e-7,1e-8),'abstol(V)':(1e-9,1e-10),'abstol(I)':(1e-14,1e-15),'maxstep':(1e-9,.5e-9)}
        checks['actual_planned_precision_profiles']=all(np.isclose(headers[i].get(k,float('nan')),v[i],atol=0,rtol=1e-8) for k,v in wanted.items() for i in [0,1])
        checks['actual_same_method_environment']=all(headers[0].get(k)==headers[1].get(k) for k in ['version','method','temp','tnom','relref','errpreset','lteratio','gmin','cmin'])
        checks['actual_gear_lte1_cthresh1p']=all(x.get('method')=='gear2only' and x.get('lteratio')==1 for x in headers) and all(p['cthresh_log_values']==['1e-12'] for p in profiles.values())
        full=all(x[0][0]==0 and abs(x[0][-1]-4.1e-6)<1e-20 for x in [a,b])
        lo=max(a[0][0],b[0][0]);hi=min(a[0][-1],b[0][-1]);domain=[float(lo),float(hi)]
        grid=np.union1d(a[0],b[0]);grid=grid[(grid>=lo)&(grid<=hi)]
        stats,cols=h.compare(a,b,grid)
        np.savetxt(args.output/'accepted_union_differences.csv',cols,delimiter=',',header='time_s,'+','.join(h.CHANNELS),comments='',fmt='%.16e')
    checks['complete_original_0_to_4p1us_domain']=full
    checks['full_domain_all_four_channels_within_original_gate']=bool(full and stats and all(s['within_original_0p05_LSB'] for s in stats.values()))
    if not full or not checks['both_actual_exit0']:status='INCOMPLETE_NOT_QUALIFIED'
    elif not checks['full_domain_all_four_channels_within_original_gate']:status='FULL_SHORT_DOMAIN_NUMERICAL_FAIL'
    elif not checks['no_unexplained_numerical_warnings']:status='WAVEFORM_LIMIT_MET_NUMERICAL_WARNINGS_UNRESOLVED'
    elif not all(checks.values()):status='INPUT_OR_CONFIGURATION_AUDIT_FAIL'
    else:status='SHORT_DIAGNOSTIC_WITHIN_LIMIT_NOT_ADC_QUALIFIED'
    result={'status':status,'checks':checks,'original_gate_V':LIMIT,'comparison_domain_s':domain,
      'four_channel_statistics':stats,'statistics_are_partial':not full,'profiles':profiles,
      'all_noncontrol_manifest_files_unchanged':same_except_control,'analyzer_sha256':sha(Path(__file__)),
      'helper_sha256':sha(HERE.parent/'adaptive_trap_4p1us_review_r1/analyze.py'),
      'complete_ADC_qualified':False,'waveform_limit_does_not_waive_LTE_warnings':True,
      'limitations':['No time shifting, switching-edge exclusion, threshold change or modified raw evidence.',
        'Malformed/incomplete raw is not salvaged into a completed run.',
        'Global Newton tolerances and maxstep change together as the planned precision profile; individual sensitivity is not isolated.',
        'Short-domain gate cannot replace complete two-frame/twelve-frame and all ADC performance gates.']}
    (args.output/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
    files=sorted(p for p in args.output.iterdir() if p.is_file())
    (args.output/'report_sha256.json').write_text(json.dumps({p.name:sha(p) for p in files},indent=2)+'\n')
    print(json.dumps({'status':status,'checks':checks,'statistics':stats},indent=2))
if __name__=='__main__':main()
