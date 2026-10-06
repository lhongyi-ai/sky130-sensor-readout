#!/usr/bin/env python3
"""Freeze a bounded isolated native-PFET diagnostic; never invokes EDA."""
import hashlib,json,math,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
RUN=BASE.parent/'runs/task_20260924T060914240241Z/design'
HELP=BASE.parent/'runs/task_20260924T070407785387Z/vsource_help.txt'
MODEL='/opt/cadence/CDK/sky130_release_0.0.3/models/sky130.lib.spice'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 report=json.loads((BASE/'body_network_probe_review/review.json').read_text())
 event=report['mode_change_near_warning'];a=event['before'];b=event['after'];dt=b['time_s']-a['time_s']
 dSlope=(b['CONV_V']-a['CONV_V'])/dt;gSlope=(b['local_gate_V']-a['local_gate_V'])/dt
 frac=-a['external_signed_VDS_V']/(b['external_signed_VDS_V']-a['external_signed_VDS_V'])
 gate=a['local_gate_V']+frac*(b['local_gate_V']-a['local_gate_V']);damp=.02;omega=abs(dSlope)/damp;gamp=gSlope/omega
 native=(RUN/'reset1_native_bound.scs').read_text()
 match=re.search(r'XPHASE_XBCONV_XI2_XP \(CONV XPHASE_XBCONV_B VDD VDD\) pfet_01v8 w=\(32u\) \\\n\s+l=150n as=8.48p ad=8.48p ps=64.53u pd=64.53u m=\(1\)\*\(1\)',native)
 if not match:raise SystemExit('Exact original device shape not found; refuse assumed geometry')
 if 'sinedc=dc' not in HELP.read_text() or 'sinephase=0' not in HELP.read_text():raise SystemExit('Missing installed sine source support')
 evidence={'source_run':str(RUN),'source_netlist_sha256':sha(RUN/'reset1_native_bound.scs'),'source_review_sha256':sha(BASE/'body_network_probe_review/review.json'),'original_instance_exact_text':match[0],'event_before':a,'event_after':b,'derived':{'drain_slope_V_per_s':dSlope,'gate_slope_V_per_s':gSlope,'gate_at_external_vds0_V':gate,'drain_amplitude_V':damp,'gate_amplitude_V':gamp,'angular_frequency_rad_per_s':omega,'period_s':2*math.pi/omega},'qualification':'Two accepted rows estimate local slopes; this does not reproduce complete load/history or assert the finite difference is exact physical derivative.'}
 (ROOT/'shape_and_stimulus_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 cases={'matched':{'speed':1.,'gate_dynamic':True,'series_ohm':0.},'static_gate':{'speed':1.,'gate_dynamic':False,'series_ohm':0.},'slow_10x':{'speed':.1,'gate_dynamic':True,'series_ohm':0.},'finite_1ohm':{'speed':1.,'gate_dynamic':True,'series_ohm':1.}}
 for case,c in cases.items():
  freq=omega*c['speed']/(2*math.pi);period=1/freq;ga=gamp if c['gate_dynamic'] else 0.
  c.update(freq_Hz=freq,period_s=period,stop_s=4*period,drain_source_mean_V=1.8,drain_source_amplitude_V=damp,gate_source_mean_V=gate,gate_source_amplitude_V=ga,source_initial_values_V={'D':1.8+damp,'G':gate-ga},requested_crossing_slopes_V_per_s={'D':dSlope*c['speed'],'G':gSlope*c['speed'] if c['gate_dynamic'] else 0.})
  c['files']={}
  for profile,r,v,i,step in [('baseline',1e-5,1e-8,1e-13,period/1000),('strict',1e-6,1e-9,1e-14,period/2000)]:
   folder=ROOT/'cases'/case/profile;folder.mkdir(parents=True,exist_ok=True)
   dnode='D' if c['series_ohm']==0 else 'DSRC';gnode='G' if c['series_ohm']==0 else 'GSRC'
   source=f'VD ({dnode} 0) vsource type=sine dc={1.8+damp:.17g} sinedc=1.8 ampl={damp:.17g} freq={freq:.17g} sinephase=90\n'
   source+=f'VG ({gnode} 0) vsource type=sine dc={gate-ga:.17g} sinedc={gate:.17g} ampl={ga:.17g} freq={freq:.17g} sinephase=270\n'
   if c['series_ohm']:source+='RD (DSRC D) resistor r=1\nRG (GSRC G) resistor r=1\n'
   text='''// Isolated model-boundary diagnostic, never a substitute for native ADC qualification.
simulator lang=spectre
global 0
'''+f'include "{MODEL}" section=tt\n'+source+'''VS (SB 0) vsource dc=1.8
XTEST (D G SB SB) pfet_01v8 w=(32u) l=150n as=8.48p ad=8.48p ps=64.53u pd=64.53u m=(1)*(1)
'''+f'simulatorOptions options temp=27 tnom=27 reltol={r:.17g} vabstol={v:.17g} iabstol={i:.17g} gmin=1e-12 cmin=0 maxwarns=1000 maxwarnstologfile=1000 maxnotes=1000 maxnotestologfile=1000\n'+'''saveOptions options save=selected
save D G SB
'''+('save DSRC GSRC\n' if c['series_ohm'] else '')+'''save XTEST.msky130_fd_pr__pfet_01v8:int_b XTEST.msky130_fd_pr__pfet_01v8:dbnode XTEST.msky130_fd_pr__pfet_01v8:sbnode sigtype=node
save XTEST.msky130_fd_pr__pfet_01v8:vds XTEST.msky130_fd_pr__pfet_01v8:reversed XTEST.msky130_fd_pr__pfet_01v8:currents sigtype=dev
save VD:currents VG:currents VS:currents sigtype=dev
'''+f'mode_boundary tran stop={4*period:.17g} maxstep={step:.17g} errpreset=conservative method=gear2only relref=sigglobal lteratio=10\n'
   p=folder/'input.scs';p.write_text(text)
   c['files'][profile]={'relative_path':str(p.relative_to(ROOT)),'sha256':sha(p),'requested_options_reltol':r,'expected_actual_tran_reltol':r*.1,'vabstol_V':v,'iabstol_A':i,'maxstep_s':step}
 manifest={'status':'PREPARED_NOT_RUN','experiment':'Isolated identical school PFET, continuous analytic sine drives around real source/drain mode crossing','source_run':'task_20260924T060914240241Z','model_entry_reference_only':MODEL,'corner':'tt','temperature_C':27,'frozen_device_parameters':{'model':'pfet_01v8','w_m':32e-6,'l_m':150e-9,'as_m2':8.48e-12,'ad_m2':8.48e-12,'ps_m':64.53e-6,'pd_m':64.53e-6,'m':1,'source_and_bulk':'same SB node, ideal 1.8V'},'cases':cases,'run_order':'Run matched baseline then strict first. Static gate and slow controls only if those data pose a specific remaining question; finite_1ohm is an explicitly uncalibrated impedance sensitivity, not an ADC physical fix.','diagnostic_only':True,'complete_ADC':False,'full_ADC_accuracy_pass':False,'physics_not_modified':['School PDK/model including rbodymod','Native device/junction geometry','gmin/cmin and body ties'],'known_limits':['Analytic ideal drives clamp external D/G and remove original buffer/load feedback. This isolates mode/body equations and cannot predict complete ADC error.','DC starts at the sine peaks with zero derivative, so no stimulus jump is introduced at t=0. Previous full ADC charge history is intentionally not reproduced.','Drive amplitude/rate match only the measured local event; repeated 34GHz small-signal sinusoid is not the ADC clock or real system stimulus.','The 1ohm source resistance is a sensitivity control, not measured original output impedance. It changes actual terminal crossing/bias; actual D/G must be read back.','No edge deletion, time alignment, forced arbitrary IC, leakage or PDK patch.','A warning-free isolated pair is not the original ADC 0.05LSB acceptance; full native ADC must be rerun after any supported fix.'],'help_provenance':{'vsource':{'path':str(HELP),'sha256':sha(HELP),'lines':'27-30 sinedc/ampl/freq/sinephase; DC value and t=0 relation at318-327'},'tran':{'path':str(BASE.parent/'runs/probe_20260924T020824848497Z/tran_help.txt'),'sha256':sha(BASE.parent/'runs/probe_20260924T020824848497Z/tran_help.txt'),'lines':'592-614 conservative preset multiplies requested reltol by0.1; actual header must verify.'}}}
 for name in ['psf_stream.py']:
  shutil.copyfile(BASE/name,ROOT/name)
 manifest['file_hashes']={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name not in ['manifest.json','SHA256SUMS'] and '__pycache__' not in p.parts and 'results' not in p.parts}
 (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (ROOT/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts and 'results' not in p.parts))
 print('PREPARED_ONLY',ROOT,'matched baseline/strict ready; no EDA executed')
if __name__=='__main__':main()
