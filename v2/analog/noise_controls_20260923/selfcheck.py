"""Pure local algebra/input/parser checks; never Spectre or synthetic noise evidence."""
from pathlib import Path
import hashlib,json,math,tempfile
import numpy as np
from scipy.integrate import quad
from build_controls import read_config,theory,timing,build,ROOT
from analyze_controls import waves
c=read_config();th=theory(c);tm=timing(c,64,16)
assert abs(tm['pulse_width_s']-2.48e-6)<1e-18
assert abs((c['clock_rise_s']+c['clock_fall_s'])/2+tm['pulse_width_s']-2.5e-6)<1e-18
assert abs(tm['phase_offsets_s']['pre_open']-3.499e-6)<1e-18
assert abs(tm['phase_offsets_s']['post_open']-3.620e-6)<1e-18
assert abs(tm['phase_offsets_s']['late_hold']-10.9e-6)<1e-18
area=quad(lambda u:1/(1+u*u),0,np.inf,epsabs=1e-12)[0]
variance=th['one_sided_white_psd_v2_per_hz']/(2*np.pi*th['tau_s'])*area
assert abs(variance/th['single_ended_variance_v2']-1)<1e-12
assert math.isclose(th['differential_independent_variance_v2'],2*variance,rel_tol=1e-12)
with tempfile.TemporaryDirectory() as td:
 p=Path(td);m=build(p/'pilot','/example/school/model.spice','pilot');assert len(m['jobs'])==6
 assert all(x['status']=='NOT_RUN' for x in m['jobs']) and not m['simulation_launched']
 long=build(p/'production','/example/school/model.spice','production');assert len(long['jobs'])==38
 for manifest in (m,long):
  for j in manifest['jobs']:
   if j['analysis']!='tran':continue
   actual=(p/manifest['profile']/j['input_file']).read_bytes();assert hashlib.sha256(actual).hexdigest()==j['input_sha256']
   if j['noise_enabled']:
    twins=[t for t in manifest['jobs'] if t['id']==j['twin_job']];assert len(twins)==1 and twins[0]['common_input_sha256']==j['common_input_sha256']
    assert 1/j['noisefmin_hz']<j['timing']['stop_s']
   assert len(j['timing']['samples'])==3*j['n_samples']
 f=p/'scalar.psf';f.write_text('HEADER\nVALUE\n"time" 0\n"H" 0.9\n"time" 1e-6\n"H" 1.0\nEND\n')
 d=waves(f,'time',['H']);assert len(d['time'])==2
 f.write_text('HEADER\nVALUE\n"time" 0\n"H" 0.9\n"time" 1e-6\nEND\n')
 try:waves(f,'time',['H']);raise RuntimeError('Missing-wave result was accepted')
 except AssertionError:pass
 f.write_text('HEADER\nVALUE\n"freq" 1000\n"I" (0 -1e-6)\n"freq" 10000\n"I" (0 -1e-5)\nEND\n')
 d=waves(f,'freq',['I']);assert np.iscomplexobj(d['I']) and d['I'][0].imag<0
report={'status':'LOCAL_PREPARATION_CHECK_PASS','spectre_executed':False,'checks':['kT/C integral and PSD units','exact midpoint/edge/strobe timing','6 pilot and 38 production job manifests','common hashes agree for off/on twins','noisefmin duration constraint','all 3 phases have required sample counts','PSF real and complex parser','missing sample fails closed'],'theory':th,'qualification':'NOT_RUN_IN_SPECTRE'}
(ROOT/'local_check_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
