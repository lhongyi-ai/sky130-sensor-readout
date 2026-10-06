#!/usr/bin/env python3
"""Prepare only the equation-equivalent ideal ground-source representation test."""
from pathlib import Path
import difflib, hashlib, json, re, shutil, subprocess
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'native_ref_finer_4p1us_r1/finer'
TARGET=HERE/'finer'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writej(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def main():
    assert not TARGET.exists(),'Never overwrite an existing prepared input folder'
    m=json.loads((SOURCE/'manifest.json').read_text())
    assert all(sha(SOURCE/n)==v for n,v in m['files_sha256'].items()),'Frozen source hash mismatch'
    TARGET.mkdir()
    for n in m['files_sha256']:shutil.copy2(SOURCE/n,TARGET/n)
    old=(SOURCE/'p2_ams_reset1.vams').read_text()
    removed='    V(vss) <+ 0.0;\n'
    assert old.count(removed)==1
    marker='  // Equation-equivalent external reference source impedance and decoupling.\n'
    assert old.count(marker)==1
    inserted='  // Same ideal zero-volt branch to simulator global ground, native representation.\n  p2_ground_fixture ground_ref(.VSS(vss));\n\n'
    new=old.replace(removed,'').replace(marker,inserted+marker)
    (TARGET/'p2_ams_reset1.vams').write_text(new)
    ground='simulator lang=spectre\n// External ideal testbench ground branch only; no circuit or source value change.\nglobal 0\nsubckt p2_ground_fixture (VSS)\nVGND (VSS 0) vsource dc=0 type=dc\nends p2_ground_fixture\n'
    (TARGET/'ground_fixture.scs').write_text(ground)
    old_control=(SOURCE/'amsdControl.scs').read_text()
    new_control=old_control.replace('include "reference_fixture.scs"','include "reference_fixture.scs"\ninclude "ground_fixture.scs"').replace('amsd {','amsd {\n portmap subckt=p2_ground_fixture\n config cell=p2_ground_fixture use=spice')
    assert old_control.count('include "reference_fixture.scs"')==1 and old_control.count('amsd {')==1
    (TARGET/'amsdControl.scs').write_text(new_control)
    oldrun=(SOURCE/'run.sh').read_text()
    assert oldrun.count('reset1_native_bound.scs reference_fixture.scs amsdControl.scs > run_input_sha256.txt')==1
    newrun=oldrun.replace('reset1_native_bound.scs reference_fixture.scs amsdControl.scs > run_input_sha256.txt','reset1_native_bound.scs reference_fixture.scs ground_fixture.scs amsdControl.scs > run_input_sha256.txt')
    (TARGET/'run.sh').write_text(newrun)
    unchanged={n:sha(SOURCE/n)==sha(TARGET/n) for n in m['files_sha256'] if n not in ['p2_ams_reset1.vams','amsdControl.scs','run.sh']}
    remaining_old=[s for s in old.splitlines() if '<+' in s and s+'\n'!=removed]
    remaining_new=[s for s in new.splitlines() if '<+' in s]
    checks={'original_input_hashes_match':True,'all_other_inputs_unchanged':all(unchanged.values()),
      'exactly_one_original_zero_volt_contribution':old.count(removed)==1,
      'old_zero_volt_contribution_removed':removed not in new,
      'all_other_analog_contributions_identical':remaining_old==remaining_new,
      'exactly_one_new_ground_instance':new.count('p2_ground_fixture ground_ref(.VSS(vss));')==1,
      'ground_negative_terminal_is_global_zero':'global 0\n' in ground and '(VSS 0) vsource dc=0 type=dc' in ground,
      'no_new_ground_port_on_chip':unchanged['reset1_native_bound.scs'],
      'same_source_voltage_no_resistor_or_noise_element_added':len(re.findall(r'^VGND ',ground,re.M))==1 and not re.search(r'^\w+ \([^\n]+\) (resistor|capacitor)',ground,re.M),
      'exact_original_finer_analysis_settings':new_control.split('adc_closure_tran tran ',1)[1].split('\n',1)[0]==old_control.split('adc_closure_tran tran ',1)[1].split('\n',1)[0]}
    assert all(checks.values()),checks
    diff=[]
    for n in ['p2_ams_reset1.vams','amsdControl.scs','run.sh']:
        diff+=difflib.unified_diff((SOURCE/n).read_text().splitlines(True),(TARGET/n).read_text().splitlines(True),fromfile='original_finer/'+n,tofile='native_ground_finer/'+n)
    diff+=difflib.unified_diff([],ground.splitlines(True),fromfile='/dev/null',tofile='native_ground_finer/ground_fixture.scs')
    (HERE/'single_factor_representation.diff').write_text(''.join(diff))
    files=sorted(list(m['files_sha256'])+['ground_fixture.scs'])
    manifest={'status':'PREPARED_NOT_RUN','diagnostic_only':True,'profile':'finer','stop_s':4.1e-6,
      'expected_completed_frames':0,'expected_completed_decisions':0,
      'change':'Only ideal zero-volt vss-to-global-ground source representation: remove V(vss)<+0, add one native DC0 vsource in an external fixture. All remaining sources/settings unchanged.',
      'hypothesis':'VAMS ideal ground branch representation may contribute to vss_flow Newton difficulty. The symbol may aggregate other VAMS contributions, so replacing this branch need not remove that unknown or fix the failure.',
      'source_manifest_sha256':sha(SOURCE/'manifest.json'),'source_directory':str(SOURCE),
      'removed_exact_VAMS_line':removed.rstrip('\n'),
      'chip_native_741_sha256':sha(TARGET/'reset1_native_bound.scs'),
      'files_sha256':{n:sha(TARGET/n) for n in files},
      'expected_actual_reltol':1e-8,'expected_actual_vabstol':1e-10,'expected_actual_iabstol':1e-15,
      'expected_actual_maxstep_s':.5e-9,'expected_method':'gear2only','expected_lteratio':1,'expected_cthresh_F':1e-12,
      'original_numerical_gate_V':.05*.8/4096,'ground_source_noise_change':False,
      'noise_scope':'This ideal zero-voltage branch adds no resistor or explicit noise source. Earlier native-reference resistor noise distinction remains.',
      'not_a_precision_pair':'Compare first with preceding same-precision finer representation; a separate same-representation precision pair is required for qualification.'}
    writej(TARGET/'manifest.json',manifest)
    (TARGET/'SHA256SUMS').write_text(''.join(f'{sha(TARGET/n)}  {n}\n' for n in files+['manifest.json']))
    subprocess.run(['bash','-n',str(TARGET/'run.sh')],check=True)
    writej(HERE/'preparation_audit.json',{'status':'PREPARED_NOT_RUN','checks':checks,'unchanged_files':unchanged,
      'remaining_analog_contributions':remaining_new,'single_factor_diff_sha256':sha(HERE/'single_factor_representation.diff'),
      'manifest_sha256':sha(TARGET/'manifest.json'),'EDA_started':False,'builder_sha256':sha(Path(__file__))})
    print(json.dumps({'checks':checks,'manifest_sha256':sha(TARGET/'manifest.json')},indent=2))
if __name__=='__main__':main()
