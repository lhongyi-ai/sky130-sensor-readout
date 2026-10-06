#!/usr/bin/env python3
"""Assemble current factual qualification state from preserved run artifacts."""
import hashlib,json,re,shutil
from pathlib import Path
R=Path(__file__).resolve().parent

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(name,data):
 p=R/name;content=json.dumps(data,indent=2,ensure_ascii=False)+'\n'
 if p.exists():
  assert p.read_text()==content, 'Conflicting existing review: '+str(p)
  return
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
def read(name):return json.loads((R/name).read_text())

pure=read('private_runtime/pure_spectre_acquire_001/local_analysis_002/summary.json')
ams=read('private_runtime/ams_acquire_alignment_001/local_analysis_002/summary.json')
put('acquisition_diagnosis/pure_saved_waveform_summary.json',pure)
put('acquisition_diagnosis/ams_saved_waveform_summary.json',ams)
actual={k:pure['actual_solver_header'][k] for k in pure['actual_solver_header']};assert actual==ams['actual_solver_header']
diff={k:(ams['half_supply_crossings'][k][0]['time_s']-pure['half_supply_crossings'][k][0]['time_s']) for k in pure['half_supply_crossings']}
finaldiff={k:ams['final_values'][k]-pure['final_values'][k] for k in pure['final_values'] if k!='time'}
put('acquisition_diagnosis/alignment_review.json',{
 'status':'ALIGNED_FIXTURE_DIAGNOSIS_NOT_NUMERICAL_PASS','actual_solver_settings_equal':True,'actual_solver':actual,
 'half_supply_crossing_time_difference_s_AMS_minus_pure':diff,
 'final_voltage_difference_V_AMS_minus_pure':finaldiff,
 'observed_logic_dead_time_s':pure['half_supply_crossings']['ACQ'][0]['time_s']-pure['half_supply_crossings']['CONV'][0]['time_s'],
 'initial_latch':{'Q_V':pure['initial_values']['Q'],'QB_V':pure['initial_values']['QB'],'eval_V':0,'assessment':'Symmetric retained-decision NAND latch DC point before first comparator evaluation. Its later state is not an ADC decision.'},
 'limitations':['Both runs triggered automatic LTE relaxation; agreement does not validate numerical precision.','Half-supply dead time does not prove absence of analog TG overlap.','EVAL and DAC bits held zero; no conversion or digital events in these two runs.'],
 'raw':{'pure':{'sha256':pure['raw_sha256'],'bytes':pure['raw_bytes'],'sample_points_including_t0':pure['sample_count']},'ams':{'sha256':ams['raw_sha256'],'bytes':ams['raw_bytes'],'sample_points_including_t0':ams['sample_count']}}
})

runs=[]
for name,logname,kind in [('ams_adc_004','xrun.log','ACTUAL_RTL_PLUS_ADC_TWO_FRAME_ATTEMPT'),('pure_spectre_acquire_001','spectre.out','ACQUISITION_ISOLATION_PURE'),('ams_acquire_alignment_001','xrun.log','IDENTICAL_ACQUISITION_ISOLATION_AMS')]:
 d=R/'private_runtime'/name;s=(d/logname).read_text();m=re.search(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?',s)
 assert m
 x={'run':name,'kind':kind,'simulator_exit':int((d/'exit_code.txt').read_text()),'spectre_summary':dict(zip(['errors','warnings','notices'],map(int,m.groups()))),'log_sha256':sha(d/logname),'automatic_lte_relaxation':('SPECTRE-16780' in s),'solver_qualification':'NOT_PASSED'}
 if name=='ams_adc_004':x.update({'simulation_status':'TIMEOUT_AT_FIRST_ACQUISITION','requested_stop_s':40e-6,'last_logged_time_s':4.06327e-6,'wall_limit_s':300,'actual_conversion_decisions':len((d/'ams_decisions.csv').read_text().splitlines())-1,'adc_two_frames':'NOT_PASSED'})
 else:x.update({'simulation_status':'REACHED_8US_WITH_AUTOMATIC_LTE_RELAXATION','stop_s':8e-6,'accepted_steps':int(re.search(r'Number of accepted tran steps\s*=\s*(\d+)',s).group(1)),'spectre_elapsed_s':float(re.search(r'Simulation started at:.*?elapsed time \(wall clock\): ([\d.]+) s',s).group(1))})
 runs.append(x)
put('acquisition_diagnosis/run_status.json',runs)

D=R/'convergence_diagnostic_1';D.mkdir(exist_ok=False)
s=(R/'private_runtime/pure_spectre_acquire_001/input.scs').read_text()
s=re.sub(r'include "[^"]+sky130.lib.spice" section=tt','include "__SCHOOL_MODEL_ENTRY__" section=tt',s)
assert 'delay=4.0625u rise=1n fall=1n' in s
s=s.replace('delay=4.0625u rise=1n fall=1n','delay=4.058u rise=10n fall=10n')
s=s.replace('maxstep=2n errpreset=conservative','maxstep=2n errpreset=conservative reltol=1e-6')
(D/'input.scs.in').write_text(s)
put('convergence_diagnostic_1/provenance.json',{'status':'PREPARED_NOT_RUN','baseline':'pure_spectre_acquire_001','circuit_sha256':sha(R/'private_runtime/pure_spectre_acquire_001/adc_native_bound.scs'),'changes':[{'field':'SAMPLE_CMD rise/fall','before_s':1e-9,'after_s':1e-8},{'field':'delay','before_s':4.0625e-6,'after_s':4.058e-6,'purpose':'Keep first rising half-supply time at 4.063us.'},{'field':'tran reltol','requested_explicit':1e-6,'baseline_actual':1e-6,'purpose':'Prevent preset from obscuring effective tolerance; no precision relaxation.'}],'unchanged':['native ADC/phase graph and all sizes','all resistances/capacitances/source impedances','initial voltages','8us stop/maxstep2ns','abs V10nV/I100fA','actual reltol1e-6','digital decisions absent'],'pass_scope':'Diagnostic only: check Newton/LTE warnings and overshoot sensitivity. No ADC accuracy, conversion, M2 or M3 acceptance.'})

cells=[{'cell':'p2adc_core_school_r1','status':'RETAINED_FAILED_CDF_SIZE_AUDIT','reason':'Startup PMOS requested 0.42um clamped to0.55um; do not use as source of passing results.','primitive_count':679},
 {'cell':'p2adc_core_fix1_school_r1','status':'NATIVE_CONNECTIVITY_AND_SIZE_AUDIT_PASS','primitive_count':679,'ports':26,'schematic_check_errors':0,'schematic_check_warnings':0,'audit':'native_adc_r1_fix1_audit.json'},
 {'cell':'p2adc_phase_school_r1','status':'NATIVE_CONNECTIVITY_AND_SIZE_AUDIT_PASS','primitive_count':48,'ports':7,'schematic_check_errors':0,'schematic_check_warnings':0,'audit':'native_phase_r1_audit.json'},
 {'cell':'p2adc_frontend_school_r3','status':'NATIVE_CONNECTIVITY_AND_SIZE_AUDIT_PASS_WITH_DOCUMENTED_SCHEMATIC_WARNINGS','primitive_count':111,'ports':9,'schematic_check_errors':0,'schematic_check_warnings':2,'warning':'Existing XPGA_XOTA_BP compatibility net has only the far terminal of1M resistor. Source topology preserved.','audit':'native_frontend_r3_audit.json'}]
put('STATUS.json',{'updated':'2026-09-23','scope':'Native ADC/phase migration, interface qualification, and bounded acquisition numerical diagnosis','native_cells':cells,'all_schematic_symbol_ports':'native_views_review.json','mixed_signal_environment':'Actual Xcelium/Spectre licenses, native Spectre binding, electrical-logic interfaces passed independent RC qualification.','actual_ADC_two_frames':'NOT_PASSED_TIMEOUT_FIRST_ACQUISITION_ZERO_DECISIONS','acquisition_isolation':'Both pure and AMS reach8us with automatic LTE relaxation; solver precision not qualified.','runs':runs,'joint_frontend_ADC':'838 real native primitives bound with originalRTL anddata_gain; prepared, not simulated.','joint_entry':'joint_prepared/manifest.json','proposed_next_diagnostic':'convergence_diagnostic_1/provenance.json','private_raw_archive':{'file':'private_runtime/adc_acquisition_evidence_1.tar.gz','sha256':sha(R/'private_runtime/adc_acquisition_evidence_1.tar.gz'),'excludes':'xcelium.d andinput.ahdlSimDB vendor-generated caches; no schoolPDK orrule files copied.'},'remaining_gates':['First real conversions and numerical-convergence baseline/strict comparison','True settling/noise, fullcode/INL/DNL,16384 samples,45PVT,200mismatch per frozen requirements','School4x4MIM compatible CDAC/core layout andDRC/LVS/PEX','Top-level post-layout performance; digital real gate power/timing and reference supply accounting'],'not_claimed':['M2complete','M3complete','ADCperformancepass','physicalsignoff','siliconmeasurements']})
print(json.dumps({'runs':runs,'max_half_crossing_delta_s':max(map(abs,diff.values()))},indent=2))
