"""Synthetic interpolation/edge checks only; no synthetic circuit acceptance data."""
from pathlib import Path
import json,numpy as np
from review import crossing_events,loop_metrics
checks=[]
f=np.array([1.,10.,100.,1000.,10000.]);a=np.array([.5,2.,.5,2.,.5]);L=a*np.exp(1j*np.pi/3)
native={'phaseMargin':60.,'phaseMarginFreq':np.sqrt(1000*10000.),'gainMargin':None,'gainMarginFreq':None,'state_verbatim':'SYNTHETIC_TEST_ONLY'}
r=loop_metrics(f,L,native);assert len(r['all_observed_unity_crossings'])==4 and r['native_crosschecks']['phaseMargin']['matched_candidate_index']==3
assert r['native_crosschecks']['phaseMargin']['match'];checks.append('All four unity crossings retained; native match can be fourth')
e=crossing_events([1,2,3],[-1,0,-1]);assert len(e)==1 and e[0]['direction']=='tangent_or_zero_plateau';checks.append('Exact-grid tangent retained')
e=crossing_events([1,2,3,4],[-1,0,0,1]);assert len(e)==1 and e[0]['event']=='exact_zero_interval' and e[0]['frequency_hz'] is None;checks.append('Zero plateau reported as interval')
e=crossing_events([1,2,3],[0,-1,1]);assert len(e)==2 and e[0]['direction']=='endpoint_zero';checks.append('Endpoint and interior crossings retained')
native={'phaseMargin':None,'phaseMarginFreq':None,'gainMargin':None,'gainMarginFreq':None,'state_verbatim':'SYNTHETIC_TEST_ONLY'}
r=loop_metrics([1,10,100],[-2+1j,-2-1j,-3-2j],native);assert r['all_observed_real_axis_crossings'][0]['axis']=='negative';assert r['raw_L_endpoints']['low']['raw_L']['real']==-2;checks.append('Negative real-axis crossing recorded without sign flip')
native={'phaseMargin':None,'phaseMarginFreq':None,'gainMargin':-20*np.log10(2),'gainMarginFreq':np.sqrt(10),'state_verbatim':'SYNTHETIC_TEST_ONLY'}
r=loop_metrics([1,10,100],[2+1j,2-1j,3-2j],native);assert r['native_crosschecks']['gainMargin']['match'];checks.append('Positive real-axis native GM convention preserved')
r=loop_metrics([1,10,100],[0,2j,.5j],{'phaseMargin':None,'phaseMarginFreq':None,'gainMargin':None,'gainMarginFreq':None,'state_verbatim':'SYNTHETIC_TEST_ONLY'});assert r['zero_magnitude_samples']==1 and len(r['all_observed_unity_crossings'])==2;checks.append('Magnitude zero handled without nonfinite JSON')
json.dumps(r,allow_nan=False)
report={'status':'LOCAL_ALGORITHM_CHECK_PASS','synthetic_tests_only':True,'spectre_run':False,'checks':checks}
Path(__file__).with_name('local_algorithm_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
