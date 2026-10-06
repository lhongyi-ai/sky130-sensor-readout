"""Analyze actual PSF-ascii results; never generates stochastic circuit waveforms."""
from pathlib import Path
import argparse,hashlib,json,re,math
import numpy as np
from scipy.stats import chi2,t as student_t

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def waves(path,axis,names):
 text=Path(path).read_text();assert '\nVALUE\n' in text,'Missing PSF VALUE section'
 requested=set(names)|{axis};rows=[];row=None
 for line in text.split('\nVALUE\n',1)[1].splitlines():
  m=re.fullmatch(r'"([^"]+)"\s+(.+)',line.strip())
  if not m or m[1] not in requested:continue
  value=m[2].strip()
  if value.startswith('('):
   a=value.strip('()').split();assert len(a)==2;value=complex(float(a[0]),float(a[1]))
  else:value=float(value)
  if m[1]==axis:
   if row is not None:assert set(row)==requested;rows.append(row)
   row={}
  assert row is not None and m[1] not in row
  row[m[1]]=value
 if row is not None:assert set(row)==requested;rows.append(row)
 assert rows,'No samples found'
 out={k:np.array([r[k] for r in rows]) for k in requested}
 assert all(np.isfinite(v).all() for v in out.values()),'Nonfinite samples'
 assert not np.iscomplexobj(out[axis]) and np.all(np.diff(out[axis])>0),'Axis invalid'
 return out

def sampled(path,job):
 d=waves(path,'time',['HP','HN','ACQ','ACQB']);target=np.array([r['time_s'] for r in job['timing']['samples']]);axis=d['time']
 i=np.searchsorted(axis,target);i=np.clip(i,0,len(axis)-1);ip=np.maximum(i-1,0);i=np.where(abs(axis[ip]-target)<abs(axis[i]-target),ip,i)
 error=abs(axis[i]-target);assert max(error)<1e-13,'Required strobe absent: do not interpolate switched samples'
 # Exact saved clock values catch phase or pulse-width mistakes.
 for k,row in enumerate(job['timing']['samples']):
  high=row['phase']=='pre_open'
  assert abs(d['ACQ'][i[k]]-(1.8 if high else 0))<1e-5,'Incorrect acquisition phase'
  assert abs(d['ACQB'][i[k]]-(0 if high else 1.8))<1e-5,'Incorrect complementary phase'
 return {k:v[i] for k,v in d.items()},float(max(error))

def moments(x):
 x=np.asarray(x,dtype=float);n=len(x);assert n>=8 and np.isfinite(x).all();mean=float(x.mean());z=x-mean;var=float(np.dot(z,z)/(n-1));assert var>0
 lag=min(100,n//5);rho=np.array([np.dot(z[:-k],z[k:])/np.dot(z,z) for k in range(1,lag+1)])
 # Initial-positive pair sum: descriptive effective sample count for the mean.
 positive=0.
 for i in range(0,len(rho)-1,2):
  pair=float(rho[i]+rho[i+1])
  if pair<=0:break
  positive+=pair
 neff_mean=min(float(n),n/max(1,1+2*positive))
 # Gaussian/autocorrelation approximation, explicitly not an exact confidence interval.
 neff_var=n/(1+2*sum((1-np.arange(1,lag+1)/n)*rho**2));dof=max(2.,neff_var-1)
 exact=[(n-1)*var/chi2.ppf(.975,n-1),(n-1)*var/chi2.ppf(.025,n-1)]
 approx=[dof*var/chi2.ppf(.975,dof),dof*var/chi2.ppf(.025,dof)]
 q=n*(n+2)*sum(rho**2/(n-np.arange(1,lag+1)));p=float(chi2.sf(q,lag))
 se=math.sqrt(var/neff_mean);half=float(student_t.ppf(.975,max(2,neff_mean-1))*se)
 return dict(n=n,mean_v=mean,rms_about_mean_v=math.sqrt(var),sample_variance_v2=var,
   mean_ci95_approx_v=[mean-half,mean+half],variance_ci95_iid_gaussian_v2=exact,
   variance_ci95_correlated_gaussian_approx_v2=approx,effective_n_mean_approx=neff_mean,effective_n_variance_approx=neff_var,
   autocorrelation_lags=rho.tolist(),ljung_box_lags=lag,ljung_box_p_approx=p,
   correlation_review_required=p<.01 or neff_mean<.8*n,
   assumptions='IID Gaussian chi-square interval is exact only under independence/Gaussianity; effective-N intervals are descriptive approximations, not proof of independence.')

def load_run(run):
 s=json.loads((run/'status.json').read_text())
 if s['status']!='PASS':
  r=json.loads((run/'execution_review.json').read_text())
  assert r['review_status']=='EXECUTION_CONFIRMED' and r['execution_status']=='PASS'
  assert r['original_status_sha256']==sha(run/'status.json') and r['spectre_log_sha256']==sha(run/'spectre.out')
  s['execution_review']=r
 assert sha(run/'input.scs')==s['input_sha256']
 return s

def tran(a):
 on=load_run(a.on_run);off=load_run(a.off_run);j=on['job'];t=off['job']
 assert j['noise_enabled'] and not t['noise_enabled'] and j['twin_job']==t['id']
 assert j['common_input_sha256']==t['common_input_sha256'],'Off/on twins differ in circuit, timing, or numerical settings'
 for key in ('model_entry_sha256','model_section'):assert on.get(key)==off.get(key),'Different model/corner between twins'
 d,err=sampled(a.on_data,j);b,errb=sampled(a.off_data,t);expected=on['theory']['single_ended_variance_v2'];rows=[]
 phases=np.array([r['phase'] for r in j['timing']['samples']]);xp=d['HP']-b['HP'];xn=d['HN']-b['HN']
 for phase in ('pre_open','post_open','late_hold'):
  mask=phases==phase;record={'phase':phase,'noise_off_deterministic_offset_p_v':float(np.mean(b['HP'][mask]-.9)),'noise_off_deterministic_offset_n_v':float(np.mean(b['HN'][mask]-.9)),
   'noise_off_span_p_v':float(np.ptp(b['HP'][mask])),'noise_off_span_n_v':float(np.ptp(b['HN'][mask]))}
  for tag,x,factor in [('p',xp,1),('n',xn,1),('differential',xp-xn,2)]:
   metric=moments(x[mask]);metric['variance_over_nominal_kTC']=metric['sample_variance_v2']/(factor*expected)
   metric['rc_10pct_center_target_met']=bool(.9<=metric['variance_over_nominal_kTC']<=1.1) if j['kind']=='rc' else None
   record[tag]=metric
  record['pn_correlation']=float(np.corrcoef(xp[mask],xn[mask])[0,1]);rows.append(record)
 return dict(status='PILOT_ONLY' if j['profile']=='pilot' else 'ANALYZED_NOT_QUALIFIED',job=j['id'],execution_warning_review=on.get('execution_review',on.get('warning_review')),theory=on['theory'],method='Actual noisy samples minus matched deterministic twin; no synthetic noise added',
   formal_adc_or_mismatch_pass=False,raw_hashes={'on':sha(a.on_data),'off':sha(a.off_data)},max_strobe_error_s=max(err,errb),phases=rows,
   remaining='Need complete bandwidth/numerical/seed convergence matrix and warning review; TG thermal kT/C is a benchmark, not an exact nonlinear signoff criterion.')

def noise(a):
 s=load_run(a.run);assert s['job']['kind']=='rc_noise';d=waves(a.data,'freq',['out']);f=d['freq'];asd=d['out'];assert not np.iscomplexobj(asd) and np.all(asd>=0)
 th=s['theory'];factor=2 if a.differential else 1;psd=factor*th['one_sided_white_psd_v2_per_hz']/(1+(2*np.pi*f*th['tau_s'])**2)
 rel=float(np.max(abs(asd**2/psd-1)));meas=float(np.trapezoid(asd**2,f));lo,hi=f[0],f[-1];exact=factor*th['single_ended_variance_v2']*2/np.pi*(np.arctan(2*np.pi*hi*th['tau_s'])-np.arctan(2*np.pi*lo*th['tau_s']))
 return dict(status='CONTROL_CHECK_PASS' if rel<.01 and abs(meas/exact-1)<.01 else 'FAIL',scope='LTI ideal RC noise units only',raw_sha256=sha(a.data),psd_max_relative_error=rel,integrated_variance_v2=meas,analytic_in_band_variance_v2=float(exact),psf_out_interpretation='ASD V/sqrt(Hz); square before integrating over Hz',formal_adc_or_mismatch_pass=False)

def mim(a):
 s=load_run(a.run);assert s['job']['kind']=='mim_ac';d=waves(a.data,'freq',['VCAP:p']);f=d['freq'];y=-d['VCAP:p'];ceff=np.imag(y)/(2*np.pi*f)
 assert np.isfinite(ceff).all() and np.all(ceff>0),'Sign/unit/model error'
 low=ceff[f<=1e6];nom=s['theory']['C_f']
 return dict(status='CONTROL_CHECK_PASS' if abs(float(np.median(low))/nom-1)<.05 else 'REVIEW_REQUIRED',scope='Effective MIM capacitance check only',raw_sha256=sha(a.data),low_frequency_median_f=float(np.median(low)),nominal_f=nom,frequency_hz=f.tolist(),ceff_f=ceff.tolist(),conductance_s=np.real(y).tolist(),formal_adc_or_mismatch_pass=False)

def main():
 p=argparse.ArgumentParser();sp=p.add_subparsers(dest='mode',required=True)
 q=sp.add_parser('tran');q.add_argument('--on-run',type=Path,required=True);q.add_argument('--off-run',type=Path,required=True);q.add_argument('--on-data',type=Path,required=True);q.add_argument('--off-data',type=Path,required=True)
 for name in ('noise','mim'):
  q=sp.add_parser(name);q.add_argument('--run',type=Path,required=True);q.add_argument('--data',type=Path,required=True)
  if name=='noise':q.add_argument('--differential',action='store_true')
 p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists(),'Preserve old analysis'
 try:r={'tran':tran,'noise':noise,'mim':mim}[a.mode](a)
 except (AssertionError,ValueError,KeyError,FileNotFoundError) as e:r=dict(status='FAIL_OR_MISSING_RESULT',reason=str(e),formal_adc_or_mismatch_pass=False)
 a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps({k:r[k] for k in ('status',)}))
if __name__=='__main__':main()
