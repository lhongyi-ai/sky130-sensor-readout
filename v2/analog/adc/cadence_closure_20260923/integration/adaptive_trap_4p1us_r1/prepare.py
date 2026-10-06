#!/usr/bin/env python3
"""Prepare only: retain frozen inputs, change only method=trap, launch no EDA."""
from pathlib import Path
import difflib, hashlib, json, shutil

HERE=Path(__file__).resolve().parent
CLOSURE=HERE.parents[1]
SOURCE=HERE.parent/'traponly_4p1us_r1'
GEAR=CLOSURE/'runs/task_20260924T060914240241Z/design'
HELP=CLOSURE.parents[1]/'noise_controls_20260923/doc_cache/tran_help.txt'
TRAP_RUN=CLOSURE/'runs/task_20260924T071725254673Z/design'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writej(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')

files=['amsdControl.scs','reset1_native_bound.scs','sar_controller.v',
       'p1_interfaces.vams','p2_ams_reset1.vams','p2_sequence.sv','profile.vh','run.sh']
assert all(not (HERE/p).exists() for p in ('baseline','strict','preparation_audit.json'))
audit={'status':'PREPARED_NOT_RUN','profiles':{},'source_help_sha256':sha(HELP),
       'change':'Only explicit tran method=trap versus original no-cthresh gear control.',
       'original_gate_V':.05*.8/4096,'EDA_started':False,
       'scope':'0–4.1us diagnostic, zero completed conversions, no ADC qualification.'}
help_lines=HELP.read_text().splitlines()
evidence={'help_path':str(HELP),'help_sha256':sha(HELP),'help_excerpt':[
    {'line':i+1,'text':help_lines[i]} for i in range(555,574)],'actual_notices':{}}
for profile in ('baseline','strict'):
    src=SOURCE/profile; dst=HERE/profile; dst.mkdir()
    source_manifest=json.loads((src/'manifest.json').read_text())
    for n in files:
        assert sha(src/n)==source_manifest['files_sha256'][n],(profile,n)
        shutil.copy2(src/n,dst/n)
    original=(src/'amsdControl.scs').read_text()
    assert original.count('method=traponly')==1
    gear=original.replace(' method=traponly','')
    new=original.replace('method=traponly','method=trap')
    assert 'cthresh=' not in new and 'lteratio=' not in new
    assert 'strobe' not in new and 'additionalparams' not in new
    (dst/'amsdControl.scs').write_text(new)
    if profile=='baseline':assert gear==(GEAR/'amsdControl.scs').read_text()
    else:
        baseline_gear=(GEAR/'amsdControl.scs').read_text()
        expected=baseline_gear.replace('reltol=1e-5 vabstol=1e-8 iabstol=1e-13',
                                      'reltol=1e-6 vabstol=1e-9 iabstol=1e-14').replace('maxstep=2n','maxstep=1n')
        assert gear==expected
    (dst/'change_vs_original_gear_control.diff').write_text(''.join(difflib.unified_diff(
        gear.splitlines(True),new.splitlines(True),fromfile='original_gear_control',tofile='adaptive_trap_control')))
    unchanged={n:sha(src/n)==sha(dst/n) for n in files if n!='amsdControl.scs'}
    assert all(unchanged.values())
    m={'status':'PREPARED_NOT_RUN','diagnostic_only':True,'profile':profile,
       'stop_s':4.1e-6,'expected_completed_frames':0,'expected_completed_decisions':0,
       'requested_method':'trap','expected_actual_method':'trap',
       'expected_actual_reltol':1e-6 if profile=='baseline' else 1e-7,
       'original_four_channel_gate_V':.05*.8/4096,'no_time_alignment_or_edge_exclusion':True,
       'cthresh_override':False,'lteratio_override':False,
       'source_manifest_sha256':sha(src/'manifest.json'),
       'original_gear_control_sha256':hashlib.sha256(gear.encode()).hexdigest(),
       'files_sha256':{n:sha(dst/n) for n in files},
       'single_factor':'method=trap only; original profile tolerances, inputs and circuit unchanged.'}
    writej(dst/'manifest.json',m)
    (dst/'SHA256SUMS').write_text(''.join(f'{sha(dst/n)}  {n}\n' for n in files+['manifest.json','change_vs_original_gear_control.diff']))
    audit['profiles'][profile]={'unchanged_files':unchanged,'manifest_sha256':sha(dst/'manifest.json'),
        'control_sha256':sha(dst/'amsdControl.scs'),'one_factor_diff_sha256':sha(dst/'change_vs_original_gear_control.diff')}
    log=TRAP_RUN/profile/'xrun.log'; lines=log.read_text(errors='replace').splitlines()
    at=[i for i,x in enumerate(lines) if 'Trapezoidal ringing is detected during tran analysis.' in x]
    assert len(at)==1 and 'Please use method=trap for better results and performance.' in lines[at[0]+1]
    evidence['actual_notices'][profile]={'path':str(log),'sha256':sha(log),
        'lines':[{'line':i+1,'text':lines[i]} for i in range(at[0]-1,at[0]+2)]}
writej(HERE/'tool_recommendation_evidence.json',evidence)
writej(HERE/'preparation_audit.json',audit)
print(json.dumps(audit,indent=2))
