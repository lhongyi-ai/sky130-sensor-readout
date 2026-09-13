#!/usr/bin/env python3
"""Build a scope-aware ADC evidence index; never promote block tests to ADC pass."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent
RESULTS=HERE/'results'


def read(name):
    p=RESULTS/name
    return json.loads(p.read_text()) if p.exists() else None


def main():
    suites=[]
    block=read('adc_block_summary.json')
    if block:
        base=[r for r in block['comparator'] if r['dsize']==0]
        skew=[r for r in block['comparator'] if r['dsize']!=0]
        suites += [dict(id='bare_comparator',scope='Continuously driven deterministic StrongARM only; 90 PVT signs plus 10 TT amplitude points',
                        cases=len(base),passed=sum(r['correct_decision'] and r['resolved'] for r in base),
                        failed=sum(not(r['correct_decision'] and r['resolved']) for r in base),evidence='results/adc_block_summary.json'),
                   dict(id='deliberate_geometry_skew',scope='Opposed +/-1% input width sensitivity, NOT PDK mismatch',
                        cases=len(skew),correct_decisions=sum(r['correct_decision'] for r in skew),
                        wrong_decisions=sum(not r['correct_decision'] for r in skew),evidence='results/adc_block_summary.json'),
                   dict(id='standard_tg_nominal',scope='TT1.8V27C only, 2.5us acquire plus 400ns measured hold; later physical/PVT failure supersedes any general pass claim',
                        cases=len(block['sampling']),passed=sum(r['acquire_pass_quarter_lsb'] and r['hold_pass_quarter_lsb'] for r in block['sampling']),
                        failed=sum(not(r['acquire_pass_quarter_lsb'] and r['hold_pass_quarter_lsb']) for r in block['sampling']),evidence='results/adc_block_summary.json'),
                   dict(id='cdac_nominal_transfer',scope='17 selected codes, ideal bottom reference waveforms, real MIM and top TG; NOT exhaustive ADC INL/DNL',
                        cases=len(block['cdac']),max_absolute_residual_lsb=max(abs(r['error_lsb']) for r in block['cdac']),evidence='results/adc_block_summary.json')]
    latch=read('latch_interface_summary.json')
    if latch:
        good=[all(c['resolve_250ns_pass'] and c['reset_hold_5ns_and_beyond_pass'] for c in r['cycles']) for r in latch['cases']]
        suites.append(dict(id='retained_comparator_interface',scope='Six conditions, two repeated decisions each, real SR latch and 5fF load',cases=len(good),passed=sum(good),failed=len(good)-sum(good),
                           max_resolution_delay_s=latch['max_resolution_delay_s'],max_clock_equivalent_cap_f=latch['max_clock_equivalent_cap_f'],evidence='results/latch_interface_summary.json'))
    for file,key,scope in [('cdac_mismatch_summary.json','cdac_only_mismatch','200 PDK tt_mm CDAC pairs; capacitors measured by AC, full-code thresholds calculated by charge conservation, ideal other circuitry'),
                           ('comparator_mismatch_summary.json','comparator_only_mismatch','200 real tt_mm comparators, 1400 coarse decisions; not whole ADC MC'),
                           ('comparator_calibration_vt_summary.json','comparator_fixed_calibration_vt','Per-comparator nominal offset estimate frozen for four V/T extremes; not complete ADC calibration'),
                           ('preamp_summary.json','preamp_characterization','Self-biased preamp OP/AC, stationary noise, driven-input overload recovery'),
                           ('preamp_reset_noise_summary.json','preamp_reset_noise','Nominal stationary preamp noise with real reset StrongARM load and no SR-latch operating-point ambiguity'),
                           ('preamp_floating_pvt_partial_summary.json','old_preamp_floating_pvt_partial','Intentionally stopped old 90-case matrix; six complete output files, not a new-LVT-reference qualification'),
                           ('preamp_floating_pvt_summary.json','preamp_floating_pvt','45 PVT x two central-code signs; single trial, not full conversions')]:
        result=read(file)
        if result:
            keep={k:v for k,v in result.items() if k not in ['samples','cases','pvt_conditions','overload_recovery_checks','source_sha256']}
            suites.append(dict(id=key,scope=scope,evidence='results/'+file,reported=keep))
    for p in sorted(RESULTS.glob('analog_wrapper_*summary.json')):
        r=json.loads(p.read_text())
        suites.append(dict(id=p.stem,scope='Six single-trial transistor-wrapper tests with ideal external finite-edge phases/codes, not complete ADC conversion',
                           cases=len(r['cases']),passed=r['pass_count'],failed=r['fail_count'],evidence=str(p.relative_to(HERE))))
    stable=read('comparator_offset_stable_refinement_r2.json')
    if stable:
        valid=[r for r in stable if r['offset_bracket_v'] is not None and r['all_resolved'] and r['monotonic']]
        centers=[sum(r['offset_bracket_v'])/2 for r in valid]
        suites.append(dict(id='comparator_bounded_nominal_offsets',scope='200 comparator-only instances, second identical-input decision per level, completed stable refinement round 2; not a whole ADC calibration',
                           cases=len(stable),bracketed=len(valid),unbracketed=len(stable)-len(valid),
                           max_bracket_width_without_guard_v=max(r['offset_bracket_v'][1]-r['offset_bracket_v'][0] for r in valid),
                           guard_each_end_v=5e-6,max_offset_estimate_uncertainty_with_guard_v=max((r['offset_bracket_v'][1]-r['offset_bracket_v'][0])/2+5e-6 for r in valid),
                           offset_estimate_min_v=min(centers),offset_estimate_max_v=max(centers),offset_estimate_sigma_v=statistics.stdev(centers),
                           later_finer_round_status='Incomplete: 150-second wall-clock limit during shared-resource run, not an electrical pass/fail',
                           evidence='results/comparator_offset_stable_refinement_r2.json'))
    for p in sorted(RESULTS.glob('reference_switch*summary.json')):
        r=json.loads(p.read_text())
        suites.append(dict(id=p.stem,scope=r['evidence_level'],completed_cases=r['completed_cases'],planned_cases=r['planned_cases'],
                           failed_diagnostic_cases=sum(not(x['acquisition_quarter_lsb'] and x['reference_quarter_lsb']) for x in r['cases']),
                           evidence=str(p.relative_to(HERE)),note='Keep actual MSB vs minimum-size counterexample and fixed vs tracking reference common mode separate.'))
    sources={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*')) if p.is_file() and p.suffix in ['.spice','.py','.md']}
    summary=dict(schema_version=1,updated_utc=datetime.now(timezone.utc).isoformat(),status='BLOCK_AND_INTEGRATION_DEVELOPMENT_NOT_ADC_QUALIFIED',
                 source_hashes_current=sources,summary_scope='Owned ADC analog blocks only; full live-RTL conversion evidence is separately under v2/integration/results',
                 cadence_used=False,tapeout_or_silicon_measurement=False,full_adc_qualification_pass=False,
                 full_adc_simulations_in_this_directory=0,suites=suites,
                 interfaces=dict(analog_wrapper_pin_order='INP INN Q QB SAMPLE SAMPLEB ACQ CONV EVAL B11 B10 B9 B8 B7 B6 B5 B4 B3 B2 B1 B0 RP RN VCM VDD VSS',
                                 output_polarity='Q high iff sampled input differential exceeds current offset-binary trial threshold',
                                 threshold_volts='0.8*trial_code/4096 - 0.4',
                                 external_phase_contract='SAMPLE opens top path first, then ACQ opens bottom acquisition paths, then CONV closes reference paths; EVAL is delayed until residual settles; Q holds through EVAL reset'),
                 remaining_ideal_elements=['External voltage/clock sources are test fixtures, not claimed on-chip implementations',
                                          'Standalone fixed-code/phase benches do not implement SAR sequencing; actual RTL bridge lives in v2/integration',
                                          'Top-level VCM/VREF sources external by specification, finite reference R/C must be included in accuracy claims'],
                 failed_or_unfinished=['Standard-Vt TG fails low-voltage cold PVT acquisition in separately retained physical tests',
                                       'Unbuffered floating-CDAC comparator flips some quarter-LSB inputs from switching interaction; independent preamp candidate improves the tested six points',
                                       'Reference-switch small TG sizing/PVT acquisition is not yet qualified',
                                       'No full-ADC stochastic transient device noise/SNDR qualification',
                                       'No exhaustive transistor-ADC all-code INL/DNL or no-missing-code demonstration',
                                       'No 200-instance whole-ADC/PGA Monte Carlo',
                                       'No complete ADC layout, DRC/LVS or top-level extracted performance',
                                       'Early behavioral B-source SAR harness was aborted/superseded by real-RTL co-simulation, not a passing result'],
                 provenance_note='Current source hashes are not retroactive run hashes. New runs have individual provenance JSON and source snapshots; earlier result JSON with embedded source hashes retain those actual historical hashes. Preserve failure/history logs.')
    (HERE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    manifest={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts}
    (HERE/'manifest.json').write_text(json.dumps(dict(generated_utc=datetime.now(timezone.utc).isoformat(),files=manifest),indent=2)+'\n')
    print(json.dumps(dict(status=summary['status'],suites=len(suites),manifest_files=len(manifest)),indent=2))


if __name__=='__main__':main()
