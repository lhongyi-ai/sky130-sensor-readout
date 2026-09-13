#!/usr/bin/env python3
"""Create a bounded, same-revision phase-delivery report; no chip completion claim."""
import hashlib
import json
from run_frontend import HERE,validate_log

frozen=HERE/'results/frozen_fdda10'
source=HERE/'results/fdda10_dual_cascode/loops_tt_1.8_27_g16/frontend_snapshot.spice'
sha=hashlib.sha256(source.read_bytes()).hexdigest()
names={
 'nominal_dc':'linearity_tt_1.8_27_g16_r1_sw',
 'fixed_cal_hot_low_vdd':'linearity_tt_1.62_85_g16_r1_sw',
 'fixed_cal_cold_high_vdd':'linearity_tt_1.98_-20_g16_r1_sw',
 'sampling':'sampling_tt_1.8_27_g16_r1_sw_iso2800.0',
 'noise':'noise_tt_1.8_27_g16_r1_sw_iso2800.0',
 'gain1_smoke':'gain_tt_1.8_27_g1_r1_sw',
 'gain4_smoke':'gain_tt_1.8_27_g4_r1_sw'}
items={}
for label,name in names.items():
    folder=frozen/name
    if label=='sampling':
        retry=HERE/'results/frozen_fdda10_step2'/name
        if (retry/'summary.json').exists():
            folder=retry
    summary=folder/'summary.json'
    if not summary.exists():
        log=folder/('sampling.log' if label=='sampling' else name.split('_',1)[0]+'.log')
        status='NO_COMPLETE_RESULT'
        error=None
        if log.exists():
            try:
                validate_log(log)
            except RuntimeError as exc:
                status='FAILED_OR_INCOMPLETE_SIMULATION'
                error=str(exc)[-1000:]
        items[label]={'status':status,'path':str(folder.relative_to(HERE)),'error':error}
        continue
    data=json.loads(summary.read_text())
    validate_log(folder/(data['test']+'.log'))
    if data['circuit_sha256']!=sha:
        raise ValueError(f'Cross-revision result is not allowed in frozen suite: {folder}')
    items[label]={'status':'SIMULATION_COMPLETED_NOT_AUTOMATIC_SPEC_PASS','path':str(summary.relative_to(HERE)),'result':data}

nom=items.get('nominal_dc',{}).get('result',{})
noise=items.get('noise',{}).get('result',{})
sample=items.get('sampling',{}).get('result',{})
noise_cal=None
if nom and noise:
    noise_cal=abs(nom['calibration_coefficients'][0])*noise['output_noise_1_to_1e+09Hz_rms_v']
gates={
 'nominal_g16_dc_1LSB':nom.get('holdout_1LSB_gate',False),
 'fixed_cal_hot_low_vdd_4LSB':items.get('fixed_cal_hot_low_vdd',{}).get('result',{}).get('fixed_calibration_4LSB_gate',False),
 'fixed_cal_cold_high_vdd_4LSB':items.get('fixed_cal_cold_high_vdd',{}).get('result',{}).get('fixed_calibration_4LSB_gate',False),
 'g16_sampling_settling_and_common_mode':all(sample.get(k,False) for k in ['all_dynamic_samples_pass','all_post_aperture_samples_pass','common_mode_within_50mV']),
 'static_noise_budget_screen_113uV':noise_cal is not None and noise_cal<=113e-6,
 'frontend_vdd_dc_budget_1p85mW':bool(noise and noise['dc_power_w']<=1.85e-3),
 'gain1_small_signal_polarity':items.get('gain1_smoke',{}).get('result',{}).get('correct_closed_loop_polarity',False),
 'gain4_small_signal_polarity':items.get('gain4_smoke',{}).get('result',{}).get('correct_closed_loop_polarity',False)}
report={'status':'UNQUALIFIED_FROZEN_PHASE_DELIVERY','circuit_sha256':sha,
 'frozen_source':str(source.relative_to(HERE)),
 'live_source_matches_freeze':hashlib.sha256((HERE/'frontend_fdda.spice').read_bytes()).hexdigest()==sha,
 'all_expected_simulations_complete':all('result' in i for i in items.values()),
 'all_expected_tests_attempted':all((frozen/name/'experiment_config.json').exists() for name in names.values()),
 'gates':gates,'calibration_normalized_static_noise_rms_v':noise_cal,
 'tests':items,'fully_qualified_frontend':False,'chip_complete':False,
 'interface':{'subckt':'sky130_v2_switchable_pga','pins':['VINP','VINN','OUTP','OUTN','VDD','VSS','VCM','SEL0','SEL1'],
              'gain_codes':{'00':1,'01':4,'10':16,'11':'reserved/disconnected'},
              'sample_driver_subckt':'sky130_v2_switchable_sample_driver','required_RISO_override_ohm':2800,
              'reservoir_cap_pf_per_side':4,'source_ohm_per_leg':350},
 'caveats':['Noise is continuous-time small-signal noise at the DC equilibrium, not proven stable sampled-system noise.',
            'The113uV frontend screen reserves an estimated63uVADCpreamp,56uVquantization and10uVsampling; it is not measured systemSNDR.',
            'Common-mode scalar return ratio includes coupled/possiblyRHPplant effects; no formal60degree dual-loop signoff.',
            'ThreeTT voltage/temperature DC conditions, not45corners; G1/G4 onlyOP/small-signal gain.',
            'NoCadence, noXschemdrawing, nofrontendDRC/LVS/PEX, no200-samplefrontendmismatch, nofullSARco-simulation in this owned suite.'],
 'next_design_work':['Close common-mode loop including positive feedback through input-pair tail-current modulation.',
                     'Fix full-range static residual while preserving noise and power budgets; do not change frozen acceptance limits.',
                     'Requalify allgains, trueADCload, numerics, startup, interference, mismatch andPVT beforelayout.']}
(HERE/'results/frozen_delivery.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'all_expected_simulations_complete':report['all_expected_simulations_complete'],'gates':gates,'noise_calibrated_v':noise_cal,'qualified':False},indent=2))
