#!/usr/bin/env python3
"""Audit existing PZ runs and read-only model metadata; never run simulations."""
from pathlib import Path
import hashlib
import json
import re
from collections import Counter

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
ROOT=REPO/'v2/cadence/linuxlab_20260923'
RUNS=ROOT/'runs'
BASE=RUNS/'spectre_poles_20260923T101120120043Z'
MIXED=RUNS/'spectre_numerical_20260923T101257881344Z'
CONTROL=RUNS/'spectre_poles_freq_control_20260923T114253639995Z'
R5=RUNS/'spectre_noise_screen_20260923T112728045435Z'
HASHES={}


def track(p):
    HASHES[str(p.relative_to(REPO))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return p.read_text()


def poles(s):
    assert '"units" "Hz"' in s
    data={int(n):complex(float(x),float(y)) for n,x,y in re.findall(r'"Pole_(\d+)" "PoleAndQ" \(\n\((\S+) (\S+)\)',s)}
    assert len(data)==104 and set(data)==set(range(1,105))
    return data


def summary(p):
    return {'saved_pole_count':len(p),'RHP_count':sum(z.real>0 for z in p.values()),
        'imaginary_axis_count':sum(z.real==0 for z in p.values()),
        'rightmost_real_hz':max(z.real for z in p.values()),
        'poles_hz':{str(n):{'real':z.real,'imag':z.imag} for n,z in p.items()}}


def actual_models(run):
    text=track(run/'input.raw/dcOpInfo.info').split('\nVALUE\n')[1]
    rows=re.findall(r'^"([^\"]+)" "bsim4" \(\n(.*?)\n\) PROP\(\n"model" "([^\"]+)"',text,re.M|re.S)
    assert len(rows)==55
    counts=Counter();bins={}
    for name,_,model in rows:
        family=re.search(r'(?:n|p)fet_01v8(?:_lvt)?',model).group(0)
        counts[family]+=1;bins.setdefault(family,set()).add(model.split('__model.')[1])
    return {'actual_bsim4_instances':55,'family_counts':dict(counts),
            'selected_bin_ids_by_family':{k:sorted(v,key=int) for k,v in bins.items()}}


def main():
    out=HERE/'pz_model_dynamic_flags_independent_review.json'
    if out.exists():raise SystemExit('Preserve prior evidence.')
    track(Path(__file__).resolve())
    flags=json.loads(track(HERE/'school_model_dynamic_flags_readonly.json'))
    wrappers=json.loads(track(HERE/'school_model_dynamic_instance_metadata.json'))
    helpmeta=json.loads(track(HERE/'spectre_bsim4_dynamic_help_metadata.json'))
    track(ROOT/'doc_cache/pz_help.txt')
    assert helpmeta['returncode']==0
    hashes_by_file={f['relative_path']:f['sha256'] for f in flags['files']}
    families={}
    for f in flags['files']:
        if not f['model_declaration_count']:continue
        n=f['model_declaration_count']; family=f['relative_path'].split('/')[1]
        expected={'acnqsmod':'0.0','trnqsmod':'0.0','rgatemod':'0.0','rbodymod':'1.0',
                  'rdsmod':'0.0','capmod':'2.0'}
        for key,value in expected.items(): assert f['flags'][key]['value_counts']=={value:n}
        wf=next(z for z in wrappers['files'] if z['relative_path']==f['relative_path'])
        assert wf['sha256']==f['sha256'] and wf['version_value_counts']=={'4.5':n}
        assert len(wf['primitive_mos_calls'])==1 and not wf['primitive_mos_calls'][0]['dynamic_flag_overrides']
        families[family]={'model_bin_count':n,'version':'4.5','flags':{k:float(v) for k,v in expected.items()},
                          'primitive_instance_dynamic_overrides':{},'model_file_sha256':f['sha256']}
    for wf in wrappers['files']:assert hashes_by_file[wf['relative_path']]==wf['sha256']
    base_native=track(BASE/'native_netlist');control_native=track(CONTROL/'native_netlist')
    assert base_native==control_native
    base_deck=track(BASE/'input.scs');mixed_deck=track(MIXED/'input.scs');deck=track(CONTROL/'input.scs')
    assert 'dc_pivot_check=yes' in deck
    assert not re.search(r'\bgmin\s*=',deck) and not re.search(r'\balter\b',deck)
    statements=re.findall(r'^(qz\d+) pz (.*)$',deck,re.M)
    assert statements==[(f'qz{f}',f'method=qz docancel=no freq={f}') for f in [1,1000,1000000]]
    assert 'gmin=1e-14' in mixed_deck and 'freq=1M' in mixed_deck
    assert not re.search(r'\bgmin\s*=',base_deck)
    data={f:poles(track(CONTROL/'input.raw'/f'qz{f}.pz')) for f in [1,1000,1000000]}
    comparisons={}
    for f in [1000,1000000]:
        differences=[(abs(data[f][n]-z)/abs(z),abs(data[f][n]-z),n) for n,z in data[1].items()]
        worst=max(differences)
        comparisons[str(f)]={'matching_method':'Same saved Pole_N index; 103/104 complex entries exactly identical.',
            'exactly_equal_pole_count':sum(data[f][n]==z for n,z in data[1].items()),
            'max_relative_difference':worst[0],'absolute_difference_at_worst_hz':worst[1],
            'worst_pole_index':worst[2]}
    old={}
    for key,run in [('r1_freq1_defaultgmin',BASE),('r1_freq1M_gmin10f_mixed',MIXED)]:
        old[key]=summary(poles(track(run/'input.raw/allPoles.pz')))
        track(run/'spectre.out')
    log=track(CONTROL/'spectre.out');track(CONTROL/'completion.json');track(CONTROL/'provenance.json')
    warnings=re.findall(r'WARNING: BSIM4 MOS Transistor[^\n]+',log)
    assert len(warnings)==3
    report={'status':'LIMITED_FREQ_SENSITIVITY_CHECK_PASSED_WARNING_ORIGIN_NOT_FULLY_RESOLVED',
        'installed_spectre_version':'21.1.0.132.isr1',
        'read_only_model_metadata':families,
        'model_metadata_time_scope':'Current school files queried after these runs. File paths match logged inputs, and two current reads have identical hashes; historical runs did not freeze these model hashes.',
        'actual_instance_families':{'r1':actual_models(BASE),'r5':actual_models(R5)},
        'controlled_freq_run':str(CONTROL.relative_to(REPO)),
        'identical_r1_native_body':True,'gmin':'default, log confirms1pS for all three PZ analyses',
        'dc_pivot_check':True,'sweep_or_alter_between_pz_analyses':False,
        'analysis_results':{str(f):summary(p) for f,p in data.items()},
        'versus_1hz':comparisons,'spectre_warning_count':len(warnings),
        'log_completion':re.search(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?\.',log).groups(),
        'old_confounded_comparison':old,
        'interpretation':[
            'AC and transient NQS are explicitly off, gate-resistance model off, substrate resistance network on. No selected MOS wrapper instance overrides these flags.',
            'rbodyMod=1 enables a substrate resistor network; that flag alone is not evidence of frequency-varying equivalent G/C. Ordinary lumped R/C dynamics must not be confused with the PZ warning definition.',
            'The installed help explains NQS selectors and frozen-equivalent PZ, but does not document the exact Spectre BSIM4 warning trigger. Its source-code gate was not available for inspection; do not assert the warning is unconditional or harmless.',
            'At this one r1 TT27 static operating condition, changing only component evaluation frequency1Hz,1kHz,1MHz gives the same104 saved poles and0RHP, with only the slowest pole moving<=0.002Hz at saved precision.',
            'This rules out large observed sensitivity over those three evaluation settings, not all frequencies, all corners, or omitted model dynamics. The warning remains in all three analyses.',
            'Earlier1Hz and1MHz runs also changed gmin and analysis sequence, so their slow-pole shift cannot be attributed to evaluation frequency.',
            'Do not reuse these r1 poles as a r5 result or as the exact complete-RHP reference count for a coupled-loop proof. That stronger claim remains unverified.'],
        'primary_external_reference':{'title':'Cadence explanation of PZ Component Eval Frequency',
            'url':'https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/43123/pole-zero-analyses-in-cadence-ade-spectra/1364485'},
        'hashes':HASHES}
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'families':families,'comparison':comparisons,'strong_RHP_reference_claim':'UNVERIFIED'},indent=2))


if __name__=='__main__':main()
