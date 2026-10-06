#!/usr/bin/env python3
"""One-time frozen first-edge diagnostic; does not modify the source design."""
from pathlib import Path
import hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parent
CLOSURE=ROOT.parents[2]
SRC=CLOSURE/'runs/task_20260924T060914240241Z/design/reset1_native_bound.scs'
def sha(x):return hashlib.sha256(x).hexdigest()
def record(s):return ' '.join(s.split())
s=SRC.read_text();flat=s.replace('\\\n',' ')
def block(name):
 b=re.search(r'(?m)^subckt '+name+r' \(([^\n]+)\)\n(.*?)^ends '+name+r'\s*$',flat,re.S|re.M)
 if not b:raise ValueError(name)
 rec=[record(l) for l in b[2].splitlines() if l.strip() and not l.lstrip().startswith('//')]
 return b[1].split(),rec
adcports,adc=block('sensor_adc_reset1');phaseports,phase=block('sensor_phases')
kept=[r for r in adc if not r.startswith(('XADC_XPRE_','XADC_XCMP_'))]
removed=[r for r in adc if r not in kept]
assert (len(adc),len(kept),len(removed),len(phase))==(693,606,87,48)
newports=[p for p in adcports if p not in ['Q','QB','EVAL','RST_N']]
inst_re=re.compile(r'^(\S+) \(([^)]+)\) (\S+) (.*)$')
fanout={};audit=[]
for origin,rs in [('sensor_adc_reset1',kept),('sensor_phases',phase)]:
 for r in rs:
  m=inst_re.fullmatch(r)
  if not m:raise ValueError(r)
  name,nodes,model,params=m.groups();nodes=nodes.split()
  audit.append({'source_subckt':origin,'instance':name,'nodes':nodes,'model':model,'normalized_record_sha256':sha(r.encode())})
  if origin=='sensor_adc_reset1':
   for n in ['CONV','ACQ','SAMPLE','SAMPLEB']:
    if n in nodes:
     assert len(nodes)==4 and nodes[1]==n
     fanout.setdefault(n,[]).append(name)
assert {k:len(v) for k,v in fanout.items()}=={'ACQ':78,'CONV':104,'SAMPLE':4,'SAMPLEB':4}
native='simulator lang=spectre\n// Native device records unchanged; preamp/comparator omitted only for diagnostic closure.\nsubckt sensor_sampling_load ('+' '.join(newports)+')\n'+'\n'.join(kept)+'\nends sensor_sampling_load\nsubckt sensor_phases ('+' '.join(phaseports)+')\n'+'\n'.join(phase)+'\nends sensor_phases\n'
(ROOT/'native_closed.scs').write_text(native)
P='XPHASE.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8'
base='''// Model-isolation diagnostic. No SAR conversion or full ADC qualification.
simulator lang=spectre
global 0
include "/opt/cadence/CDK/sky130_release_0.0.3/models/sky130.lib.spice" section=tt
include "native_closed.scs"
VVDD (VDD 0) vsource dc=1.8
VVCM (VCM 0) vsource dc=0.9
VRP (RPSRC 0) vsource dc=1.1
VRN (RNSRC 0) vsource dc=0.7
RRP (RPSRC RP) resistor r=1
RRN (RNSRC RN) resistor r=1
CRP (RP 0) capacitor c=10n
CRN (RN 0) capacitor c=10n
VIP (IPSRC 0) vsource dc=0.7005
VIN (INSRC 0) vsource dc=1.0995
RIP (IPSRC INP) resistor r=350
RIN (INSRC INN) resistor r=350
// Matches observed source command within 2.423pV through original 4.1us probe.
VCMD (SAMPLE_CMD 0) vsource type=pwl dc=0 wave=[0 0 4.0625u 0 4.0635u 1.8 4.1u 1.8]
'''
base+=''.join(f'VB{i} (B{i} 0) vsource dc=0\n' for i in range(11,-1,-1))
base+='XLOAD ('+' '.join('0' if p=='VSS' else 'TOP' if p=='SAMPLE' else 'TOPB' if p=='SAMPLEB' else p for p in newports)+') sensor_sampling_load\n'
base+='XPHASE (SAMPLE_CMD TOP TOPB ACQ CONV VDD 0) sensor_phases\n'
base+='''saveOptions options save=selected
save VDD VCM RPSRC RNSRC RP RN IPSRC INSRC INP INN SAMPLE_CMD TOP TOPB ACQ CONV B0 B1 B2 B3 B4 B5 B6 B7 B8 B9 B10 B11
save XLOAD.XADC_TP XLOAD.XADC_TN XPHASE.XPHASE_XBCONV_B XPHASE.XPHASE_CMD_B_DELAY XPHASE.XPHASE_ACQ_DELAY XPHASE.XPHASE_CONV_DELAY XPHASE.XPHASE_ACQ_RAW XPHASE.XPHASE_CONV_RAW XPHASE.XPHASE_TOP_RAW_B
'''
base+=f'save {P}:int_b {P}:dbnode {P}:sbnode sigtype=node\nsave {P}:vds {P}:reversed {P}:currents sigtype=dev\nsave VVDD:currents VRP:currents VRN:currents VCMD:currents sigtype=dev\n'
profiles={}
for name,r,v,i,step in [('baseline','1e-5','1e-8','1e-13','2n'),('strict','1e-6','1e-9','1e-14','1n')]:
 text=base+f'simulatorOptions options temp=27 reltol={r} vabstol={v} iabstol={i} maxwarns=1000 maxwarnstologfile=1000 maxnotes=1000 maxnotestologfile=1000\nclosed_phase tran stop=4.1u maxstep={step} errpreset=conservative relref=sigglobal method=gear2only lteratio=10\n'
 path=ROOT/f'input_{name}.scs';path.write_text(text)
 profiles[name]={'file':path.name,'sha256':sha(path.read_bytes()),'requested_reltol':float(r),'vabstol':float(v),'iabstol':float(i),'maxstep_s':float(step[:-1])*1e-9,'note':'Inspect actual run header; conservative uses0.1*requested reltol in installed21.'}
manifest={'id':'closed_phase_load_v1','scope':'FIRST_PHASE_EDGE_MODEL_ISOLATION_ONLY','expected_stop_s':4.1e-6,'expected_completed_frames':0,'complete_ADC':False,'full_ADC_accuracy_pass':False,'source_native':str(SRC),'source_native_sha256':sha(SRC.read_bytes()),'source_probe_task':'task_20260924T060914240241Z','source_ADC_instances':693,'retained_ADC_instances':606,'removed_preamp_comparator_instances':87,'retained_phase_instances':48,'total_native_instances':654,'fanout':fanout,'removed_instances':[r.split()[0] for r in removed],'records':audit,'profiles':profiles,'native_sha256':sha((ROOT/'native_closed.scs').read_bytes()),'boundary':{'CONV':'Free circuit output of unchanged native driver, with104original directly gatedMOS and their complete closed switch networks. No invented output capacitor.','removed_loading':'Preamp/comparator input loading and internal charge history omitted; this may change CDAC and phase waveforms. Must compare against actual fullprobe before claiming reproduction.','source_command':'0V through4.0625us; continuous linear1ns risingedge to1.8V; hold through4.1us. Derivative corners preserved as original command.','trial_bits':'All12ideal0V; actual fullprobe saved all12 exactly0 for all4951points. No RTL is simulated here.','input_differential_V':-.399,'each_input_source_ohm':350,'reference_source_V':{'RP':1.1,'RN':.7},'reference_feed_ohm':1,'reference_external_decoupling_F':1e-8,'reference_note':'Original external bench loads. Source supply currents include externalR/C; no chip powerPASS.','simulation_difference':'Pure Spectre replaces AMS boundary equations by equivalent constant sources,R/C and first commandPWL; no feedback decisions or reset qualification.'},'stimulus_evidence':{'original_all_accepted_points':4951,'command_analytic_max_error_V':2.4227286843370166e-12,'command_all_bits_zero':True,'tool_help':str(CLOSURE/'runs/task_20260924T070407785387Z/vsource_help.txt'),'native_records':'Every retained normalized record SHA is unchanged; native record whitespace normalized only.'}}
(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
shutil.copyfile(ROOT.parent/'psf_stream.py',ROOT/'psf_stream.py')
print('READY',ROOT,'native instances',len(audit),'CONV fanout',len(fanout['CONV']))
