#!/usr/bin/env python3
"""Audit saved real AMS evidence. Missing results never become PASS; no simulation."""
import argparse,csv,hashlib,json,math,re
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def csvrows(p):
 with p.open() as f:return list(csv.DictReader(f))
def digit(value,vdd):
 return 0 if value<=.3*vdd else 1 if value>=.7*vdd else None
SUFFIX={'VDD':'vdd','VSS':'vss','INP':'inp','INN':'inn','RP':'rp','RN':'rn','VCM':'vcm',
 'Q':'q_e','QB':'qb_e','RST_N':'rst_n_e','EVAL':'eval_e','SAMPLE_CMD':'sample_cmd_e',
 'TOP':'top_e','TOPB':'topb_e','ACQ':'acq_e','CONV':'conv_e',
 'TP':'adc.XADC_TP','TN':'adc.XADC_TN','PREP':'adc.XADC_PREP','PREN':'adc.XADC_PREN',
 'S_BAR':'adc.XADC_XCMP_S_BAR','R_BAR':'adc.XADC_XCMP_R_BAR',
 'BP0':'adc.XADC_BP0','BN0':'adc.XADC_BN0','BP11':'adc.XADC_BP11','BN11':'adc.XADC_BN11'}

def scan_psf(path,requests):
 """Stream full accepted trace. Interpolate requested instants without time shifting."""
 aliases={};alias=None;active=False;header={};cur=None;prev=None;samples=[];ranges={};count=0
 pending=iter(sorted(requests,key=lambda r:r['time_s']));wanted=next(pending,None)
 actual_names={}
 def finish(row):
  nonlocal prev,wanted,count
  if row is None:return
  if set(row)!={'time',*SUFFIX}:raise ValueError('Missing selected analog trace(s): '+str(sorted(set(SUFFIX)-set(row))))
  if prev and row['time']<prev['time']:raise ValueError('Nonmonotonic saved time')
  count+=1
  for k,v in row.items():
   if not math.isfinite(v):raise ValueError('Nonfinite saved '+k)
   if k not in ranges:ranges[k]=[v,v]
   else:ranges[k]=[min(v,ranges[k][0]),max(v,ranges[k][1])]
  while wanted and wanted['time_s']<=row['time']+1e-18:
   t=wanted['time_s']
   if prev is None:
    if abs(t-row['time'])>1e-18:raise ValueError('Request predates first saved time')
    point=dict(row);bracket=[row['time'],row['time']]
   else:
    a,b=prev['time'],row['time']
    if t<a-1e-18:raise ValueError('Request skipped')
    factor=0 if b==a else (t-a)/(b-a)
    point={k:prev[k]+factor*(row[k]-prev[k]) for k in row};bracket=[a,b]
   samples.append(dict(wanted,volts=point,interpolation_bracket_s=bracket))
   wanted=next(pending,None)
  prev=row
 with path.open() as f:
  for line in f:
   if line.strip()=='VALUE':active=True;continue
   if not active:
    g=re.match(r'^"([^"]+)" GROUP (\d+)\s*$',line)
    if g:
     if g[2]!='1':raise ValueError('Unsupported multitrace PSF group')
     alias=g[1];continue
    if alias:
     g=re.match(r'^"([^"]+)"\s+"[^"]+"',line)
     if not g:raise ValueError('Malformed PSF trace alias')
     aliases[alias]=g[1];alias=None;continue
   m=re.match(r'^"([^"]+)"\s+([-+.0-9eE]+)\s*$',line)
   if not m:continue
   name,value=m[1],float(m[2])
   if not active:header[name]=value;continue
   if name=='time':finish(cur);cur={'time':value};continue
   name=aliases.get(name,name)
   for k,s in SUFFIX.items():
    if name.lower()==('p2_ams_reset1.'+s).lower():
     if k in actual_names and actual_names[k]!=name:raise ValueError('Ambiguous trace '+k)
     actual_names[k]=name
     if cur is None:raise ValueError('Trace precedes time')
     cur[k]=value;break
 finish(cur)
 if wanted:raise ValueError('Incomplete waveform: missing request '+str(wanted))
 if not count:raise ValueError('No ASCII transient samples')
 return {'sample_count':count,'saved_interval_s':ranges.pop('time'),'actual_solver_header':header,
         'selected_trace_names':actual_names,'ranges_V':ranges,'samples':samples,'raw_sha256':sha(path)}

def analyze(run,raw=None):
 manifest=json.loads((run/'manifest.json').read_text());n=manifest['frames'];errors=[]
 hashes={}
 for name,expected in manifest['generated_file_hashes'].items():
  p=run/name
  got=sha(p) if p.exists() else None
  hashes[name]={'expected':expected,'actual':got}
  if got!=expected:errors.append('Frozen run input differs: '+name)
 try:exitcode=int((run/'simulator_exit_code.txt').read_text().strip())
 except (FileNotFoundError,ValueError):exitcode=None
 logs='\n'.join(p.read_text(errors='replace') for p in [run/'driver.log',run/'xrun.log'] if p.exists())
 marker=re.search(r'P2_HANDSHAKE_PASS frames=(\d+) accepted=(\d+) aborted=(\d+) checks=(\d+) ignored_busy=(\d+) reserved=(\d+)',logs)
 counts=dict(zip(['frames','accepted','aborted','checks','ignored_busy','reserved'],map(int,marker.groups()))) if marker else None
 warning_lines=list(dict.fromkeys(l for l in logs.splitlines() if re.search(r'WARNING|Warning|Newton iteration|LTE|minimum time step|relax',l)))
 functional_marker=bool(counts and counts['frames']==n and counts['accepted']==n+1 and counts['aborted']==1 and counts['ignored_busy']>0 and counts['reserved']>0 and 'P2_FAIL' not in logs and exitcode==0)
 tables={}
 for k in ['decisions','events','frames']:
  try:tables[k]=csvrows(run/(k+'.csv'))
  except FileNotFoundError:tables[k]=[];errors.append('Missing '+k+'.csv')
 decisions,events,frames=(tables[k] for k in ['decisions','events','frames'])
 digital_checks=[];requests=[]
 for f in range(1,n+1):
  ds=[d for d in decisions if int(d['frame'])==f];fs=[d for d in frames if int(d['frame'])==f]
  ev=[e for e in events if e['event']=='accept' and int(e['frame'])==f]
  okay=len(ds)==12 and len(fs)==1 and len(ev)==1
  word=0;details=[]
  if okay:
   t0=float(ev[0]['time_ns']);g=int(ev[0]['gain']);stim=int(ev[0]['stimulus'])
   for j,d in enumerate(ds):
    expected_trial=(word<<(12-j)) | (1<<(11-j))
    bit=int(d['q']);ok=(int(d['decision'])==j and int(d['qb'])==1-bit and bit in (0,1) and int(d['trial_word'])==expected_trial and int(d['gain'])==g and int(d['stimulus'])==stim and abs(float(d['time_ns'])-(t0+(j+5)*625))<1e-6)
    okay &= ok;word=(word<<1)|bit;details.append({'decision':j,'pass':ok})
    for delta,kind in [(-1,'pre_capture'),(0,'capture')]:requests.append({'time_s':(float(d['time_ns'])+delta)*1e-9,'kind':kind,'frame':f,'decision':j,'q':bit})
   okay &= int(fs[0]['data'])==word and int(fs[0]['data_gain'])==g and abs(float(fs[0]['time_ns'])-(t0+10000))<=5.000001
   requests.append({'time_s':(t0+2500-1)*1e-9,'kind':'acquisition_end_minus_1ns','frame':f,'stimulus':stim})
  digital_checks.append({'frame':f,'pass':bool(okay),'assembled_real_Q_word':word,'actual_output':fs,'decisions':details})
 if len(decisions)!=12*n or len(frames)!=n:errors.append('Unexpected/incomplete completed frame or decision count')
 for e in events:
  if e['event']=='reset_hold':requests.append({'time_s':float(e['time_ns'])*1e-9,'kind':'global_reset_hold'})
 requests.append({'time_s':.5e-6,'kind':'initial_global_reset'})
 analog=None;analog_checks=[];sampling=[]
 if raw is None:
  candidates=list((run/'amsdControl.raw').glob('adc_closure_tran.tran.tran'))
  if len(candidates)==1:raw=candidates[0]
 if raw is not None:
  try:
   analog=scan_psf(raw,requests)
   for s in analog['samples']:
    v=s['volts'];rail=v['VDD']-v['VSS'];bits={k:digit(v[k]-v['VSS'],rail) for k in ['Q','QB','RST_N','EVAL','S_BAR','R_BAR','ACQ','TOP']}
    if s['kind'] in ['pre_capture','capture']:
     q=s['q'];okay=bits['Q']==q and bits['QB']==1-q and bits['RST_N']==1
     # S/R activation BEFORE the capture is necessary; reset's preset Q is insufficient.
     if s['kind']=='pre_capture':okay &= bits['EVAL']==1 and bits['S_BAR']==(0 if q else 1) and bits['R_BAR']==(1 if q else 0)
     analog_checks.append({'time_s':s['time_s'],'kind':s['kind'],'frame':s['frame'],'decision':s['decision'],'pass':bool(okay),'logic_from_saved_analog':bits,'volts':v,'interpolation_bracket_s':s['interpolation_bracket_s']})
    elif 'global_reset' in s['kind']:
     okay=bits['Q']==0 and bits['QB']==1 and bits['RST_N']==0
     analog_checks.append({'time_s':s['time_s'],'kind':s['kind'],'pass':okay,'logic_from_saved_analog':bits,'volts':v})
    elif s['kind']=='acquisition_end_minus_1ns':
     errors_v={k:v[k]-v['INP' if k.startswith('BP') else 'INN'] for k in ['BP0','BP11','BN0','BN11']}
     sampling.append({'frame':s['frame'],'time_s':s['time_s'],'bottom_plate_minus_input_V':errors_v,'maximum_observed_bottom_error_V':max(map(abs,errors_v.values())),'top_minus_vcm_V':{'TP':v['TP']-v['VCM'],'TN':v['TN']-v['VCM']},'TP_minus_TN_V':v['TP']-v['TN'],'reference_V':{k:v[k] for k in ['RP','RN','VCM']},'phase_logic':{k:bits[k] for k in ['ACQ','TOP']},'scope':'Selected endpoint/LSB/MSB diagnostics only, not full-CDAC convergence or post-switch acquisition-error acceptance.'})
  except (ValueError,KeyError,IndexError) as exc:errors.append('Analog evidence incomplete: '+str(exc))
 else:errors.append('Missing known-format PSF ASCII; no analog qualification')
 code_diagnostics=[]
 for fr in frames:
  stim=int(fr['stimulus']);diff=([-0.399,0.399] if n==2 else [-0.399,-.32,-.24,-.16,-.08,-.001,.001,.08,.16,.24,.32,.399])[stim]
  ideal=max(0,min(4095,math.floor((diff+.4)/(.8/4096))))
  code_diagnostics.append({'frame':int(fr['frame']),'commanded_differential_V':diff,'raw_code':int(fr['data']),'ideal_offset_binary_bin_floor':ideal,'raw_minus_ideal_LSB':int(fr['data'])-ideal,'scope':'Uncalibrated diagnostic, no accuracy or linearity acceptance inferred from these few codes.'})
 functional=bool(functional_marker and not errors and len(digital_checks)==n and all(c['pass'] for c in digital_checks) and analog_checks and all(c['pass'] for c in analog_checks))
 return {'status':'BOUNDED_FUNCTIONAL_PASS_PRECISION_NOT_QUALIFIED' if functional else 'NOT_PASSED','simulator_exit_code':exitcode,'handshake_marker_counts':counts,'functional_pass':functional,'errors':errors,'digital_checks':digital_checks,'analog_decision_reset_checks':analog_checks,'acquisition_diagnostics':sampling,'uncalibrated_code_diagnostics':code_diagnostics,'all_retained_warning_lines':warning_lines,'numerical_log_clean':bool(exitcode==0 and not warning_lines and analog is not None),'actual_solver':analog['actual_solver_header'] if analog else None,'raw_evidence':{k:v for k,v in analog.items() if k!='samples'} if analog else None,'immutable_input_check':hashes,'unverified_gates':{'original_full_ADC_0p05_LSB_convergence':'NOT_RUN','all_code_INL_DNL':'NOT_RUN','dynamic_device_noise_SNDR':'NOT_RUN','mismatch_200_full_ADC':'NOT_RUN','PVT45':'NOT_RUN','DRC_LVS_top_PEX':'NOT_RUN'},'limitations':['A handshake/decision word consistent with real Q does not prove correct analog transfer; inspect input versus output independently.','No simulated result is generated by this analyzer.','All waveform interpolation brackets retained; no shifts or excluded switching edges can create a numerical PASS.','Digital gain is metadata in this standalone ADC fixture; analog frontend is absent.']}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--raw',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('Refusing to overwrite previous review')
 r=analyze(a.run,a.raw);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps({k:r[k] for k in ['status','simulator_exit_code','functional_pass','errors','numerical_log_clean']}));raise SystemExit(0 if r['functional_pass'] else 2)
