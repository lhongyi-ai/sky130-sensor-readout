#!/usr/bin/env python3
"""Raw signed static charge branches; no PFET sign change or inferredmodel remapping."""
from pathlib import Path
import hashlib,json,math,os
import numpy as np
from read_actual_dc import read_dc,P
ROOT=Path(__file__).resolve().parent;C=ROOT.parent.parent;RUN=C/'runs/task_20260924T080723598851Z/design/results'
PATHS={'baseline':RUN/'baseline_20260924T080725Z_2409163','strict':RUN/'strict_20260924T080811Z_2412024'}
CHARGES=['qg','qd','qs','qb','qgi','qdi','qsi','qbi'];FIELDS=CHARGES+['qjd','qjs','qgdovl','qgsovl','cgd','cdd','cbd','cgdbo','cddbo','cbdbo','int_b','dbnode','sbnode','vds','vgs','vbs','reversed']
WINDOWS=[(1e-6,5e-6),(2e-6,1e-5),(5e-6,2e-5)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def series(profile,name):
 p=PATHS[profile]/'input.raw'/f'{name}.dc';h,a,s,raw=read_dc(p)
 out=[]
 for row in raw:
  r={'axis':row[a],'external_D_minus_S_V':row['D']-row['SB'],'G':row['G'],'SB':row['SB']}
  r.update({n:row[P+':'+n] for n in FIELDS});out.append(r)
 return h,sorted(out,key=lambda r:r['external_D_minus_S_V'])
def fit(rows,q,low,high,side):
 a=[r for r in rows if low-1e-12<=side*r['external_D_minus_S_V']<=high+1e-12]
 if len(a)<3:raise ValueError('Too few samplesfor one-sidedfit')
 x=np.array([r['external_D_minus_S_V'] for r in a]);y=np.array([r[q] for r in a]);xm=float(x.mean());scale=float(x.std());u=(x-xm)/scale;yref=float(y.mean());A=np.column_stack([np.ones(len(x)),u]);coef=np.linalg.lstsq(A,y-yref,rcond=None)[0];slope=float(coef[1]/scale);intercept=float(yref+coef[0]-slope*xm);res=y-(yref+A@coef)
 return {'samples':len(a),'measured_x_range_V':[float(x.min()),float(x.max())],'slope_dQ_dExternalD_F':slope,'extrapolated_Q_at_0_C':intercept,'max_abs_fit_residual_C':float(np.max(np.abs(res))),'rms_fit_residual_C':float(np.sqrt(np.mean(res*res))),'centered_scaled_design_condition':float(np.linalg.cond(A)),'physical_x_center_V':xm,'physical_x_scale_V':scale,'reversed_values':sorted(set(r['reversed'] for r in a))}
def near(rows,x):
 r=min(rows,key=lambda r:abs(r['external_D_minus_S_V']-x))
 if abs(r['external_D_minus_S_V']-x)>1e-12:raise ValueError('Missing physicalgridpoint')
 return r

def shared(a,b):
 # Declared DCgridis shared; validateactualexternalbias difference separately. Nochargeaxis/timealignment.
 bkey={round(r['axis']/5e-7):r for r in b};pairs=[]
 for r in a:
  k=round(r['axis']/5e-7)
  if k in bkey and abs(r['axis']-bkey[k]['axis'])<1e-12:pairs.append((r,bkey[k]))
 if len(pairs)!=len(a):raise ValueError('Missingcommonbiaspoint')
 return {'points':len(pairs),'maximum_measured_external_bias_mismatch_V':max(abs(a['external_D_minus_S_V']-b['external_D_minus_S_V']) for a,b in pairs),'maximum_differences':{n:max(abs(a[n]-b[n]) for a,b in pairs) for n in FIELDS},'matching_rule':'ShareddeclaredVDELTAgrid within1pV, reportactualD−Sdifference; noextrapolation, nochange torawcharges.'}
def main():
 data={};headers={}
 for p in PATHS:
  inv=json.loads((ROOT/f'{p}_inventory.json').read_text())
  assert inv['exit_code']==0 and inv['model_hashes_before_after_equal'] and inv['model_hash_comparison_exit']==0
  assert all(s['point_count_matches'] and s['missing_requested_OP_fields']==['ig','is','ib'] for s in inv['sweeps'].values())
  for d in ['up','down']:
   h,r=series(p,'dc_fine_'+d);data[p+'_'+d]=r;headers[p+'_'+d]=h
   assert h['reltol']==(1e-5 if p=='baseline' else 1e-6)
 data['strict_up_decimated_1uV']=data['strict_up'][::2];data['strict_down_decimated_1uV']=data['strict_down'][::2]
 fits={};secants={};scope={}
 for label,rows in data.items():
  fits[label]={};secants[label]={};scope[label]={'saved_total_intrinsic_max_diff_C':{a+'minus'+b:max(abs(r[a]-r[b]) for r in rows) for a,b in zip(['qg','qd','qs','qb'],['qgi','qdi','qsi','qbi'])},'nonzero_overlap_charge_ranges_C':{n:[min(r[n] for r in rows),max(r[n] for r in rows)] for n in ['qgdovl','qgsovl']},'body_minus_external_bulk_max_V':{n:max(abs(r[n]-r['SB']) for r in rows) for n in ['int_b','dbnode','sbnode']},'sum_four_raw_q_max_abs_C':max(abs(sum(r[n] for n in ['qg','qd','qs','qb'])) for r in rows),'note':'Rawfieldalgebra only; noindependentphysicalchargeconservationclaim.'}
  zero=near(rows,0.)
  for q in CHARGES:
   fits[label][q]=[]
   for low,high in WINDOWS:
    neg=fit(rows,q,low,high,-1);pos=fit(rows,q,low,high,1)
    fits[label][q].append({'window_abs_D_minus_S_V':[low,high],'negative':neg,'positive':pos,'positive_minus_negative_slope_F':pos['slope_dQ_dExternalD_F']-neg['slope_dQ_dExternalD_F'],'positive_minus_negative_zero_extrapolation_C':pos['extrapolated_Q_at_0_C']-neg['extrapolated_Q_at_0_C'],'actual_zero_charge_C':zero[q]})
   secants[label][q]=[]
   for e in ([5e-7] if len(rows)==4001 else [])+[1e-6,2e-6,5e-6,1e-5]:
    l=near(rows,-e);r=near(rows,e)
    secants[label][q].append({'epsilon_V':e,'left_slope_F':(zero[q]-l[q])/(zero['external_D_minus_S_V']-l['external_D_minus_S_V']),'right_slope_F':(r[q]-zero[q])/(r['external_D_minus_S_V']-zero['external_D_minus_S_V'])})
 samples={label:[near(rows,x) for x in [-2e-5,-5e-6,-1e-6,0,1e-6,5e-6,2e-5]] for label,rows in data.items()}
 compare={'baseline_up_vs_down':shared(data['baseline_up'],data['baseline_down']),'strict_up_vs_down':shared(data['strict_up'],data['strict_down']),'baseline_up_vs_strict_up_shared_grid':shared(data['baseline_up'],data['strict_up']),'baseline_down_vs_strict_down_shared_grid':shared(data['baseline_down'],data['strict_down'])}
 result={'status':'SIGNED_STATIC_BRANCH_DIAGNOSTIC_NOT_MODEL_VALIDATION','actual_headers':headers,'direction_precision_comparisons':compare,'charge_scope_observations':scope,'fits':fits,'one_sided_secants':secants,'raw_selected_bias_samples':samples,'fields_missing':['ig','is','ib'],'missing_handling':'Notfilled,replaced or claimedobserved. Charge/Cfieldsandseparatelysavedd/g/s/bcurrentsareavailable.','definitions':['All rawQsigns preserved; noPFETtype/reversed multiplication orD/Sswapping.','Fitsuse measuredexternalD−S and reportbothbranchslopes,scaledcondition,residual andwindowdependence. Decimationusesactualstrictpointswithoutinterpolation.','DC derivativesalongresolvedexternalbias anddocumented intrinsic partialC have differentreference/mapping scopes; no equalityorbugacceptance threshold.','Savedtotal/intrinsicQareidentical despite nonzero separatelysavedoverlapQ; names alone do not establishindependentcomponents.','No transientstate,LTE,loadedADCortimingconclusion isimplied.'],'complete_ADC':False,'full_ADC_accuracy_pass':False,'analysis_hashes':{p.name:sha(p) for p in [ROOT/'read_actual_dc.py',Path(__file__)]}}
 (ROOT/'branch_analysis.json').write_text(json.dumps(result,indent=2)+'\n')
 for q in ['qgi','qdi','qbi']:
  w=fits['strict_up'][q][0];print(q,'slopesfF',w['negative']['slope_dQ_dExternalD_F']*1e15,w['positive']['slope_dQ_dExternalD_F']*1e15,'interceptdeltaC',w['positive_minus_negative_zero_extrapolation_C'])
 print('crossprecisionQmaxC',max(compare['baseline_up_vs_strict_up_shared_grid']['maximum_differences'][q] for q in CHARGES))
 plot(data,result)
def plot(data,result):
 os.environ.setdefault('MPLCONFIGDIR',str(ROOT.parent/'private_runtime/matplotlib'))
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'font.size':10})
 fig,ax=plt.subplots(2,1,figsize=(11.7,8.2));fig.subplots_adjust(left=.12,right=.96,top=.82,bottom=.22,hspace=.43)
 rows=[r for r in data['strict_up'] if abs(r['external_D_minus_S_V'])<2.001e-5];z=near(rows,0)
 for q,color in [('qgi','#136ead'),('qdi','#bb4d39'),('qbi','#74448d')]:
  ax[0].plot([r['external_D_minus_S_V']*1e6 for r in rows],[(r[q]-z[q])*1e18 for r in rows],'.-',ms=2,color=color,label=q+' - q(0)')
  left=[];right=[]
  for a,b in zip(rows,rows[1:]):
   x0,x1=a['external_D_minus_S_V'],b['external_D_minus_S_V'];x=(x0+x1)/2
   # Never averageacrosszero; presentrealone-sidedintervals.
   if x0<0<x1:continue
   (left if x<0 else right).append((x*1e6,(b[q]-a[q])/(x1-x0)*1e15))
  for xx in [left,right]:ax[1].plot([x for x,y in xx],[y for x,y in xx],color=color,lw=1.4,label=q if xx is left else None)
 for a in ax:a.grid(alpha=.2);a.axvline(0,color='#647487',ls='--',lw=.8);a.set_xlabel('Measured external VD - VS (uV)')
 ax[0].set_ylabel('Raw signed charge change (aC)');ax[0].legend(frameon=False,ncol=3);ax[0].set_title('Charges remain close through zero while branch slopes change',loc='left',fontsize=11)
 ax[1].set_ylabel('One-sided secant dQ/dVD (fF)');ax[1].legend(frameon=False,ncol=3);ax[1].set_title('Static branch sensitivity survives a run with no transient integration',loc='left',fontsize=11)
 fig.text(.12,.94,'Static mode-boundary evidence narrows the next question',fontsize=17,weight='bold')
 fig.text(.12,.88,'Actual school DC, strict 0.5 uV grid; no sign correction, source/drain relabeling or cross-zero derivative.',fontsize=10.2,color='#57687a')
 fig.text(.12,.12,'This does not establish a model bug or solve ADC transient convergence.',fontsize=11.5,weight='bold')
 fig.text(.12,.055,'Total and intrinsic charge fields are identical in this output despite nonzero overlap fields. Their definition and\nterminal mapping still require care. Multiple windows, directions and precision/grid controls are retained in JSON.',fontsize=10.2,color='#57687a',linespacing=1.6)
 for ext in ['png','svg']:fig.savefig(ROOT/f'static_branch_charge.{ext}',dpi=165)
 plt.close(fig)
if __name__=='__main__':main()
