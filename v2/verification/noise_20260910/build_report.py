#!/usr/bin/env python3
"""Fail-closed report for the narrow RC engine capability, not ADC acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent


def check_rc(rows):
    by={row['name']:row for row in rows}
    names=['off','on_seed11','replay_seed11','on_seed29','on_os12','on_sde']
    complete=all(name in by and by[name]['run']['returncode']==0
                 and abs(by[name].get('end_s',0)-0.02)<1e-12 for name in names)
    if not complete:
        return {'all_checks_pass':False,'complete_runs':False}
    on=[by[name] for name in names if name!='off']
    checks={
        'complete_runs':complete,
        'noise_off_has_zero_variance':by['off']['variance_v2']<1e-24,
        # This 20% is an RC engine sanity bound, NOT a chip specification.
        'intrinsic_thermal_noise_matches_ktc_within_20_percent':all(.8<=r['variance_over_ktc']<=1.2 for r in on),
        'same_seed_replays':by['on_seed11']['waveform_sha256']==by['replay_seed11']['waveform_sha256'],
        'different_seed_changes_waveform':by['on_seed11']['waveform_sha256']!=by['on_seed29']['waveform_sha256'],
        'stationary_integral_matches_ktc_within_2_percent':all(abs(r['small_signal_integral_v2']/r['kt_over_c_v2']-1)<.02 for r in rows),
        'oversampling_change_under_10_percent':abs(by['on_os12']['variance_v2']/by['on_seed11']['variance_v2']-1)<.1,
    }
    return {'all_checks_pass':all(checks.values()),**checks}


def accept_single_device(summary, extraction):
    """Necessary, not sufficient conditions for accepting one model fixture."""
    return bool(summary.get('run',{}).get('returncode')==0
                and not summary.get('unknown_version_fallback',True)
                and extraction.get('native_bin_extraction_equivalent_at_tested_bias',False)
                and 0<=extraction.get('vacask_ac_max_relative_error',1)<1e-3
                and extraction.get('vacask_noise_max_error_db',100)<0.1)


def main():
    rc_path=HERE/'results/20260910T062307Z/summary.json'
    rc=json.loads(rc_path.read_text())
    latest=max((p for p in (HERE/'results').glob('*/summary.json') if p.parent.name[0].isdigit()),key=lambda p:p.parent.name)
    mos=json.loads(latest.read_text())['sky130_mos']
    check=check_rc(rc['rc_controls'])
    docroot=Path('/foss/tools/vacask')
    references=[docroot/'SOURCES',docroot/'share/doc/vacask/docs/cmd-analysis-trannoise.md',
                docroot/'share/doc/vacask/docs/cmd-options-tran.md',docroot/'share/doc/vacask/docs/dev-spice.md',
                docroot/'src/vacask/devices/resistor.va',docroot/'lib/vacask/mod/resistor.osdi',
                docroot/'lib/vacask/mod/spice/bsim4v8.osdi',
                docroot/'lib/vacask/python/ng2vclib/converter.py',docroot/'lib/vacask/python/ng2vclib/dfl.py']
    report={
        'status':'RC_INTRINSIC_NOISE_CAPABILITY_PASS_SKY130_PORT_INCOMPLETE' if check['all_checks_pass'] else 'NOISE_CAPABILITY_CHECK_FAILED',
        'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'adc_noise_qualified':False,'full_chain_sndr_qualified':False,
        'rc_source_report':str(rc_path.relative_to(HERE)),
        'rc_source_sha256':hashlib.sha256(rc_path.read_bytes()).hexdigest(),
        'rc_checks':check,'rc_results':rc['rc_controls'],
        'latest_sky130_attempt':str(latest.relative_to(HERE)),
        'latest_sky130_source_sha256':hashlib.sha256(latest.read_bytes()).hexdigest(),
        'sky130_attempt':mos,
        'specific_integration_gaps':[
            'Installed ng2vc has no process_instance_m implementation and no level-54 BSIM4 family mapping.',
            'Its model-name matching does not resolve SKY130 binned base names to model .N variants.',
            'A native BSIM4.8 OSDI exists but SKY130 version-4.5 parameter and geometry/bin equivalence is not demonstrated.',
            'PDK mismatch semantics, all used PMOS/LVT/passive devices, charge conservation, and noise contribution mapping are not port-qualified.',
            'No dynamic comparator decision-probability, sampled kT/C, or complete noisy ADC FFT has been run.',
            'No proven VACASK mixed-signal bridge to existing RTL in this project.'
        ],
        'allowed_claim':'A preinstalled open-source engine generates intrinsic resistor noise and passes narrow physics/reproducibility controls.',
        'forbidden_claim':'The SKY130 SAR ADC or full sensor chip has passed noise/SNDR verification.',
        'sources':[
            {'title':'Installed VACASK official source/docs a9d8860929517499299b91a0300c0f8ff2ff4716','url':'https://codeberg.org/arpadbuermen/VACASK','access':'Read bundled official files; web origin blocked crawler'},
            {'title':'ngspice official manual, transient noise sources and ordinary small-signal noise','url':'https://ngspice.sourceforge.io/docs/ngspice-manual.pdf'},
            {'title':'Xyce official analysis support','url':'https://xyce.sandia.gov/about-xyce/'}],
        'installed_evidence_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in references if p.is_file()},
        'project_sources_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')},
    }
    single=HERE/'results/single_mos_20260910T063501Z/summary.json'
    equivalence=single.parent/'numeric_equivalence.json'
    if single.exists() and equivalence.exists():
        summary=json.loads(single.read_text());extraction=json.loads(equivalence.read_text())
        report['single_bin_comparison']={
            'path':str(single.relative_to(HERE)),
            'source_sha256':hashlib.sha256(single.read_bytes()).hexdigest(),
            'numeric_extraction_equivalence_sha256':hashlib.sha256(equivalence.read_bytes()).hexdigest(),
            'summary':summary,'extraction_control':extraction,
            'model_fixture_accepted':accept_single_device(summary,extraction)}
        if check['all_checks_pass'] and not accept_single_device(summary,extraction):
            report['status']='RC_INTRINSIC_NOISE_CAPABILITY_PASS_SKY130_MODEL_MISMATCH'
        report['specific_integration_gaps'][2]='Confirmed: ngspice selects BSIM4v5 version 4.5; VACASK falls back to 4.8.3. DC/AC agree but noise PSD differs by up to 3.1444 dB at this one bias.'
    (HERE/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])


if __name__=='__main__': main()
