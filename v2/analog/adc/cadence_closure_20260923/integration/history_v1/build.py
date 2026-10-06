#!/usr/bin/env python3
"""Assemble audited reset1 + physical phase + unchanged RTL. Never run a simulator."""
import argparse, hashlib, importlib.util, json, re, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
OLD=ROOT/'v2/physical/cdac_repair_20260923/adc_native_mapping_1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
EXPECTED={
 'private_runtime/si_reset1_001/netlist':'492ab683c55598cf999d325e6cfd38ec3c520d315db6cd271c253efce87e0e4c',
 'private_runtime/si_phase_001/netlist':'51f00f498ed0e069e75bc81890c551cd8c2f8e84dab2d16f90a78e43e08386b1',
 'reset1/objects.json':'234ce979a944daf8e756c5d1028cd47e2def04d3303e6498d6aca2bd57bb1790',
 'phase_school_r1_objects.json':'f0f82235ce0498e7306b3450cb4e760a888b7c7b79915f21c077500802e70248',
 'reset1/native_audit.json':'1564596185a0a250752f7453b7bfeae0f0a03f4f53dd206e7c07bdfefc8b1bf8',
 'native_phase_r1_audit.json':'4ec25e875b04e1010a153c821f9a1bb511722643c554ffc5d6910c674b82a9df',
 'reset1/native_views_review.json':'0f610eb6bfa84651bd4327b732f5e46b70fbde974be38d0332573231d0b10349',
 'private_runtime/ams_adc_004/p1_interfaces.vams':'07e4dd5bc9e8ebe03881ee4bea686763891e59ff6d8e7e41c541c403d1803084',
 'private_runtime/ams_adc_004/p1_ams_adc_smoke.vams':'51cf6d0c7a60f709790bf2da486f9dfa9ef9a3d11a635f6ac1813586fed7047d',
 'private_runtime/ams_adc_004/run.sh':'e55525cf6c225d791c514fe2d1c91de4f9362fb3319065d7619b0d639ca1add0',
}
PORTS='INP INN Q QB SAMPLE SAMPLEB ACQ CONV EVAL B11 B10 B9 B8 B7 B6 B5 B4 B3 B2 B1 B0 RP RN VCM VDD VSS RST_N'.split()
PHASE='SAMPLE_CMD TOP TOPB ACQ CONV VDD VSS'.split()
RTL_SHA='5e65a4cff94ae8507d5830cd7c0c669be50ea6e1730b8d20b0893afc39e4dadf'

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--output',type=Path,required=True);ap.add_argument('--frames',type=int,choices=[2,12],default=2)
 ap.add_argument('--accuracy',choices=['baseline','strict'],default='baseline')
 ap.add_argument('--model',required=True,help='Explicit previously verified school model entry; path only, never copies models')
 a=ap.parse_args();out=a.output.resolve()
 if out.exists():raise SystemExit('Refusing to overwrite output')
 if any(c in a.model for c in ['"','\n','\r']) or not a.model.startswith('/'):raise SystemExit('Model must be an absolute path without quotes/newlines')
 sources={}
 for name,want in EXPECTED.items():
  p=OLD/name;got=sha(p)
  if got!=want:raise SystemExit('Frozen dependency hash changed: '+name)
  sources[str(p.relative_to(ROOT))]=got
 rtl=ROOT/'v2/rtl/sar_controller.v'
 if sha(rtl)!=RTL_SHA:raise SystemExit('RTL source changed')
 sources[str(rtl.relative_to(ROOT))]=RTL_SHA
 for local in ['build.py','p2_sequence.sv','analyze.py','run.sh']:
  sources[str((HERE/local).relative_to(ROOT))]=sha(HERE/local)
 auditor=ROOT/'v2/analog/frontend/cadence_20260923/audit_native_netlist.py'
 spec=importlib.util.spec_from_file_location('native_auditor',auditor);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 sources[str(auditor.relative_to(ROOT))]=sha(auditor)
 adc_objects=json.loads((OLD/'reset1/objects.json').read_text());phase_objects=json.loads((OLD/'phase_school_r1_objects.json').read_text())
 body=(OLD/'private_runtime/si_reset1_001/netlist').read_text();phase=(OLD/'private_runtime/si_phase_001/netlist').read_text()
 views=json.loads((OLD/'reset1/native_views_review.json').read_text())
 assert views['ports']==PORTS and views['status']=='PASS' and views['symbol_27ports_match']
 reports={}
 for name,objects,text,count in [('adc',adc_objects,body,693),('phase',phase_objects,phase,48)]:
  report=mod.audit(objects,text)
  assert report['status']=='NATIVE_NETLIST_AUDIT_PASS' and report['actual_count']==count,report['errors']
  reports[name]=report
 # Explicit source-deck binary weights and terminal contract independent of aggregate count.
 caps={o['name']:o for o in adc_objects if o['kind']=='mim'}
 weights={}
 for side in ['P','N']:
  bank=[]
  for bit in range(12):
   matches=[o for o in caps.values() if o['nets'].get('PLUS')=='XADC_T'+side and o['nets'].get('MINUS')=='XADC_B'+side+str(bit)]
   assert len(matches)==1,(side,bit)
   m=float(matches[0]['props']['m']);assert m==2**bit
   bank.append(int(m))
  matches=[o for o in caps.values() if o['nets'].get('PLUS')=='XADC_T'+side and o['nets'].get('MINUS')=='XADC_D'+side]
  assert len(matches)==1 and float(matches[0]['props']['m'])==1
  weights[side]={'bit_weights_LSB_to_MSB':bank,'dummy':1,'total':sum(bank)+1}
 # Wrap literal native bodies; no model substitution or extra primitive in either body.
 bound='simulator lang=spectre\nsubckt sensor_adc_reset1 ('+' '.join(PORTS)+')\n'+body+'\nends sensor_adc_reset1\nsubckt sensor_phases ('+' '.join(PHASE)+')\n'+phase+'\nends sensor_phases\n'
 assert 'p2adc_core_reset1_school_r1' in body and 'RST_N' in body
 top=(OLD/'private_runtime/ams_adc_004/p1_ams_adc_smoke.vams').read_text()
 top=top.replace('`include "disciplines.vams"','`include "disciplines.vams"\n`include "profile.vh"')
 top=top.replace('// UNCOMPILED AMS harness. Resolve sensor_adc_candidate and sensor_phases\n// to audited real PDK transistor subcircuits; never add dummy/behavioral stubs.','// Real reset1 ADC/native phase + unchanged SAR RTL; only boundary drivers are ideal.\n// Newly prepared harness; local syntax checks do not imply school AMS execution.')
 top=top.replace('p1_ams_adc_smoke','p2_ams_reset1').replace('sensor_adc_candidate adc','sensor_adc_reset1 adc')
 top=top.replace('electrical q_e,','electrical rst_n_e;\n  electrical q_e,')
 top=top.replace('wire [1:0] gain_sel,stimulus_sel,data_gain,gain_latched;','wire [1:0] gain_sel,data_gain,gain_latched;\n  wire [3:0] stimulus_sel;\n  wire reset_fb,reset_fb_valid;')
 top=top.replace('  analog begin','  real input_diff;\n  analog begin\n    input_diff=(`P2_FRAMES==2)?((stimulus_sel==0)?-0.399:0.399):\n      ((stimulus_sel==0)?-0.399:(stimulus_sel==1)?-0.32:(stimulus_sel==2)?-0.24:\n       (stimulus_sel==3)?-0.16:(stimulus_sel==4)?-0.08:(stimulus_sel==5)?-0.001:\n       (stimulus_sel==6)?0.001:(stimulus_sel==7)?0.08:(stimulus_sel==8)?0.16:\n       (stimulus_sel==9)?0.24:(stimulus_sel==10)?0.32:0.399);')
 top=top.replace('((stimulus_sel==0)?-0.399:0.399)/2.0','input_diff/2.0')
 top=top.replace('  p1_l2e drive_sample','  p1_l2e drive_reset(rst_n,rst_n_e,vdd,vss);\n  p1_e2l read_reset(rst_n_e,vdd,vss,reset_fb,reset_fb_valid);\n  p1_l2e drive_sample')
 top=top.replace('.RP(rp),.RN(rn),.VCM(vcm),.VDD(vdd),.VSS(vss));','.RP(rp),.RN(rn),.VCM(vcm),.VDD(vdd),.VSS(vss),.RST_N(rst_n_e));')
 top=top.replace('p1_ams_sequence seq','p2_sequence seq')
 top=top.replace('.sample_fb_valid(sample_fb_valid),.eval_fb(eval_fb),.eval_fb_valid(eval_fb_valid));','.sample_fb_valid(sample_fb_valid),.eval_fb(eval_fb),.eval_fb_valid(eval_fb_valid),\n    .reset_fb(reset_fb),.reset_fb_valid(reset_fb_valid));')
 assert 'sensor_adc_candidate' not in top and '.RST_N(rst_n_e)' in top
 accuracy={'baseline':('1e-6','1e-8','1e-13','2n'),'strict':('1e-7','1e-9','1e-14','1n')}[a.accuracy]
 config=f'''simulator lang=spectre
include "{a.model}" section=tt
include "reset1_native_bound.scs"
simulatorOptions options temp=27 reltol={accuracy[0]} vabstol={accuracy[1]} iabstol={accuracy[2]}
saveOptions options save=allpub
adc_closure_tran tran stop={40 if a.frames==2 else 150}u maxstep={accuracy[3]} errpreset=conservative
amsd {{
 portmap subckt=sensor_adc_reset1
 config cell=sensor_adc_reset1 use=spice
 portmap subckt=sensor_phases
 config cell=sensor_phases use=spice
}}
'''
 out.mkdir(parents=True)
 for name,data in [('reset1_native_bound.scs',bound),('p2_ams_reset1.vams',top),('amsdControl.scs',config),('profile.vh',f'`define P2_FRAMES {a.frames}\n')]: (out/name).write_text(data)
 for source,name in [(rtl,'sar_controller.v'),(OLD/'private_runtime/ams_adc_004/p1_interfaces.vams','p1_interfaces.vams'),(HERE/'p2_sequence.sv','p2_sequence.sv'),(HERE/'run.sh','run.sh'),(HERE/'analyze.py','analyze.py')]:shutil.copyfile(source,out/name)
 (out/'audits').mkdir()
 for key,report in reports.items():(out/'audits'/f'{key}_native_audit.json').write_text(json.dumps(report,indent=2)+'\n')
 shutil.copyfile(OLD/'reset1/native_views_review.json',out/'audits/native_views_review.json')
 provenance={'status':'PREPARED_NOT_SIMULATED','frames':a.frames,'expected_completed_decisions':12*a.frames,'expected_additional_aborted_frame':1,'accuracy_profile':a.accuracy,'source_hashes':sources,'native_primitive_counts':{'ADC':693,'phase':48},'port_order':{'ADC':PORTS,'phase':PHASE},'cdac_unit_weights':weights,'native_body_hashes':{'ADC':sha(OLD/'private_runtime/si_reset1_001/netlist'),'phase':sha(OLD/'private_runtime/si_phase_001/netlist')},'requested_solver':dict(zip(['reltol','vabstol','iabstol','maxstep'],accuracy)),'operating_condition':{'corner':'tt','temp_C':27,'VDD_V':1.8,'input_common_mode_V':0.9,'RP_source_V':1.1,'RN_source_V':0.7,'VCM_V':0.9,'source_resistance_ohm_each':350,'reference_resistance_ohm_each':1,'reference_decoupling_F_each':1e-8,'clk_Hz':1600000},'data_gain_rule':'Completed word metadata; gain_latched may change on same edge for newly accepted frame. No analog programmable frontend in this independent ADC fixture.','decision_origin':'Real Q/QB from native reset1 StrongARM/holding latch. Offline audit requires actual S/R activation for each decision; reset Q=0 is not accepted as evidence.','excluded_claims':['Full-code linearity','0.05LSB waveform convergence','16384 point noise FFT','200 full-ADC mismatch','45-point PVT','Physical layout/PEX','Complete-chip power']}
 provenance['generated_file_hashes']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
 (out/'manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')
 print(json.dumps({'output':str(out),'status':provenance['status'],'frames':a.frames,'counts':provenance['native_primitive_counts']}))
if __name__=='__main__':main()
