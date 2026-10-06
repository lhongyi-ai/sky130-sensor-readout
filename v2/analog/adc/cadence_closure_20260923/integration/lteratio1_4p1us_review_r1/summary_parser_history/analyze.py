#!/usr/bin/env python3
"""Review preserved lteratio=1 timeout, never repair/fill incomplete PSF data."""
from pathlib import Path
from collections import Counter
import hashlib, importlib.util, json, re, sys
import numpy as np
HERE=Path(__file__).resolve().parent
CLOSURE=HERE.parents[1]
RUN=CLOSURE/'runs/task_20260924T072218194124Z/design'
sys.path.insert(0,str(CLOSURE/'numerics'))
from psf_stream import Trace
spec=importlib.util.spec_from_file_location('previous_review',HERE.parent/'traponly_4p1us_review_r1/analyze.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not (HERE/'review.json').exists()
    profiles={};data={}
    for profile in ['baseline','strict']:
        run=RUN/profile; p=run/'amsdControl.raw/adc_closure_tran.tran.tran'
        tr=Trace(p);last=None;n=0;error=None
        try:
            for row in tr.rows():last=row;n+=1
        except ValueError as e:error=str(e)
        # The unmodified parser checks every saved voltage, finite values, and ordering.
        # If it fails, do not salvage/delete/fill the failed row or compare a fabricated trace.
        with p.open('rb') as f:f.seek(max(0,p.stat().st_size-256));end=f.read().rstrip().endswith(b'END')
        log=(run/'xrun.log').read_text(errors='replace')
        m=json.loads((run/'manifest.json').read_text())
        profiles[profile]={**old.logs(run),'input_hashes_match':all(sha(run/f)==h for f,h in m['files_sha256'].items()),
          'manifest_sha256':sha(run/'manifest.json'),'actual_header':tr.header,'raw_sha256':sha(p),
          'raw_byte_count':p.stat().st_size,'raw_END_present':end,'all_voltage_rows_parse_error':error,
          'all_voltage_rows_parsed':n,'voltage_trace_count':len(tr.names),
          'last_saved_time_s':None if last is None else last['time'],
          'raw_data_edited_or_filled':False,
          'complete_to_requested_stop':bool(error is None and last and abs(last['time']-4.1e-6)<1e-20),
          'error_code_counts':dict(Counter(re.findall(r'ERROR \(([^)]+)\)',log))),
          'all_error_lines':[x for x in log.splitlines() if 'ERROR (' in x],
          'newton_recovery_notice_count':log.count('Disaster recovery algorithm is enabled'),
          'last_recovery_lines':[x for x in log.splitlines() if 'Newton iteration fails to converge at time' in x][-3:],
          'final_termination_is_external_stop':'ERROR (SPECTRE-25): The simulation is stopped either by the user or the farm.' in log}
        if error is None:data[profile]=old.raw(run)
    partial_stats=None;domain=None;count=0
    if len(data)==2:
        a,b=data['baseline'],data['strict'];lo=max(a[0][0],b[0][0]);hi=min(a[0][-1],b[0][-1])
        grid=np.union1d(a[0],b[0]);grid=grid[(grid>=lo)&(grid<=hi)]
        partial_stats,columns=old.compare(a,b,grid);domain=[float(lo),float(hi)];count=len(grid)
        np.savetxt(HERE/'partial_common_domain_differences.csv',columns,delimiter=',',
          header='time_s,'+','.join(old.CHANNELS),comments='',fmt='%.16e')
    result={'status':'PARTIAL_TIMEOUT_NOT_QUALIFIED','profiles':profiles,
      'partial_common_domain_s':domain,'partial_union_count':count,
      'partial_four_channel_statistics':partial_stats,
      'threshold_V':old.LIMIT,'full_requested_0_to_4p1us_gate':'NOT_RUN_INCOMPLETE_STRICT',
      'partial_statistics_do_not_qualify_full_domain':True,'complete_ADC_qualified':False,
      'no_smaller_lteratio_retry_prepared':True,'analyzer_sha256':sha(Path(__file__)),
      'reused_analysis_helper_sha256':sha(HERE.parent/'traponly_4p1us_review_r1/analyze.py'),
      'reader_sha256':sha(CLOSURE/'numerics/psf_stream.py')}
    (HERE/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False,
      default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
    print(json.dumps({k:result[k] for k in ['status','partial_common_domain_s','partial_four_channel_statistics']},indent=2))
    for p,d in profiles.items():print(p,json.dumps({k:d[k] for k in ['Spectre_final_summary','warning_code_counts','diagnostic_statistics','last_saved_time_s','raw_END_present','all_voltage_rows_parse_error','all_voltage_rows_parsed']}))
if __name__=='__main__':main()
