#!/usr/bin/env python3
"""Meaningful negative checks only; no synthetic waveform is an ADC result."""
import hashlib, json
from pathlib import Path
import numpy as np
from analyze_pair import forced_indices, json_scalar
from psf_stream import Trace
HERE=Path(__file__).resolve().parent
def main():
    contract=json.loads((HERE/'forced_time_contract.json').read_text())
    required=np.array(contract['forced_times_fs'])*1e-15
    _,full=forced_indices(required,required)
    assert full['present_count']==2001
    _,removed=forced_indices(np.delete(required,1000),required)
    assert removed['present_count']==2000 and len(removed['missing_times_s'])==1
    _,shifted=forced_indices(required+1e-15,required)
    assert shifted['present_count']==0 # 1 fs shift is NOT accepted as common points.
    serialized=json.loads(json.dumps({'true':np.bool_(True),'false':np.bool_(False),'n':np.int64(2001),'v':np.float64(9.765625e-6)},allow_nan=False,default=json_scalar))
    assert serialized=={'true':True,'false':False,'n':2001,'v':9.765625e-6}
    try:json.dumps({'unsupported':np.array([1])},default=json_scalar)
    except TypeError:pass
    else:raise AssertionError('Arrays must not silently cross the scalar JSON boundary')
    old=HERE.parents[1]/'runs/task_20260924T053814697817Z/design/amsdControl.raw/adc_closure_tran.tran.tran'
    trace=Trace(old,wanted={'p2_ams_reset1.conv_e'});times=np.array([r['time'] for r in trace.rows()])
    _,original=forced_indices(times,required)
    assert original['present_count']<2001 # Preexisting natural samples must not impersonate requested strobe points.
    manifests={}
    for profile in ['baseline','strict']:
        folder=HERE/profile;manifest=json.loads((folder/'manifest.json').read_text())
        for name,digest in manifest['generated_file_hashes'].items():
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
        manifests[profile]=hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest()
    report={'status':'LOCAL_DIAGNOSTIC_CHECKS_PASS_NOT_CADENCE_RESULTS',
       'checks':['exact point list accepted','one missing point rejected','1 fs phase shift rejected','old natural grid cannot pass forced-point presence','both prepared manifest file hashes verified','numpy booleans/integers/floats preserve their native scalar values in JSON; arrays rejected'],
       'old_actual_unforced_probe_matching_points':original['present_count'],
       'prepared_manifest_sha256':manifests,'complete_ADC_qualified':False,'long_campaign_allowed':False}
    (HERE/'local_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
