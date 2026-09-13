#!/usr/bin/env python3
"""Offline bounded-probe audit. Does not launch a simulator."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from hybrid import PSDTable, fft_bin_edges, gaussian_samples, qualification_gate

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'noise_20260910/results/single_mos_20260910T063501Z'
N=16384
FS=100000.
K=1.380649e-23
TEMP=300.15
R=10000.
C=1e-9


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_shared_points(old_f,old_y,new_f,new_y):
    indices=np.searchsorted(new_f,old_f)
    best=[]
    for i,j in enumerate(indices):
        candidates=[q for q in [j-1,j] if 0<=q<len(new_f)]
        q=min(candidates,key=lambda q:abs(new_f[q]/old_f[i]-1))
        if abs(new_f[q]/old_f[i]-1)<1e-10:best.append((i,q))
    if not best:raise ValueError('No common frequency samples')
    errors=[abs(new_y[q]/old_y[i]-1) for i,q in best]
    return dict(shared_frequency_points=len(best),max_relative_error=float(max(errors)))


def read_case(path):
    report=json.loads((path/'summary.json').read_text())
    report['noisetran_rejected_in_log']='noisetran: no such command available in ngspice' in (path/'worker.log').read_text()
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('results',type=Path)
    args=parser.parse_args();folder=args.results.resolve()
    run_summary=json.loads((folder/'summary.json').read_text())
    names=['off_seed11','on_seed11','replay_seed11','on_seed29']
    cases={name:read_case(folder/name) for name in names}
    on=cases['on_seed11'];off=cases['off_seed11']
    ac=np.load(folder/'on_seed11/ac.npz')
    old_ac=np.load(OLD/'ngspice_ac.npz')
    old_noise=np.load(OLD/'ngspice_noise.npz')
    new_noise=np.load(folder/'on_seed11/out_noise.npz')
    old_op=json.loads((OLD/'summary.json').read_text())['ngspice_op']
    rc=np.load(folder/'on_seed11/rc_native_noise.npz')
    va=np.load(folder/'on_seed11/rc_osdi_noise.npz')
    f=rc['frequency'];native_psd=rc['amplitude_spectrum']**2
    theoretical=4*K*TEMP*R/(1+(2*np.pi*f*R*C)**2)
    rc_expected=1/(1+2j*np.pi*ac['frequency']*R*C)
    native_table=PSDTable(f,native_psd)
    native_bins=native_table.folded_bin_power(fft_bin_edges(N,FS),FS)
    exact_known=2*K*TEMP/(np.pi*C)*(np.arctan(2*np.pi*f[-1]*R*C)-np.arctan(2*np.pi*f[0]*R*C))
    expected_continuous=native_table.cumulative[-1]
    noise_table=PSDTable(new_noise['frequency'],new_noise['amplitude_spectrum']**2)
    mos_bins=noise_table.folded_bin_power(fft_bin_edges(N,FS),FS)
    model_dir=folder/'planning_model';model_dir.mkdir(exist_ok=True)
    np.savez_compressed(model_dir/'sampled_bin_variances.npz',
        bin_edges_hz=fft_bin_edges(N,FS),rc_bin_variance_v2=native_bins,
        sky130_single_mos_bin_variance_v2=mos_bins)
    model_stats={}
    for name,table,bins in [('native_rc',native_table,native_bins),('native_sky130_single_mos',noise_table,mos_bins)]:
        a=gaussian_samples(bins,N,11);b=gaussian_samples(bins,N,11);c=gaussian_samples(bins,N,29)
        np.savez_compressed(model_dir/(name+'_model_sequences.npz'),seed11=a,seed29=c)
        powers=np.array([np.mean(gaussian_samples(bins,N,seed)**2) for seed in range(1001,1129)])
        np.savez(model_dir/(name+'_128_noise_realizations.npz'),mean_square_v2=powers)
        total=float(np.sum(bins));direct=float(table.integral(0,5000))
        folded=float(table.folded_bin_power([0,5000],FS)[0])
        # Variance of record mean-square for independent Gaussian Fourier modes.
        # Interior complex modes have two DOFs; DC and Nyquist have one.
        theoretical_single_power_variance=float(np.sum(bins[1:-1]**2)+2*bins[0]**2+2*bins[-1]**2)
        standard_error=float(np.sqrt(theoretical_single_power_variance/len(powers)))
        model_stats[name]={
            'status':'FROZEN_BIAS_LTI_KNOWN_BAND_PLANNING_MODEL_ONLY',
            'record_length':N,'sample_rate_hz':FS,'noise_realizations':len(powers),
            'process_or_device_mismatch_samples':0,
            'known_analog_band_hz':[float(table.f[0]),float(table.f[-1])],
            'outside_band_noise':'UNKNOWN_NOT_ASSERTED_ZERO',
            'continuous_known_band_variance_v2':float(table.cumulative[-1]),
            'folded_all_sample_bins_variance_v2':total,
            'power_conservation_relative_error':float(abs(total/table.cumulative[-1]-1)),
            'direct_known_0_to_5khz_rms_v':float(np.sqrt(direct)),
            'folded_known_0_to_5khz_rms_v':float(np.sqrt(folded)),
            'known_0_to_5khz_alias_power_factor':folded/direct,
            'rng_same_seed_bit_exact':bool(np.array_equal(a,b)),
            'rng_different_seed_different_waveform':bool(not np.array_equal(a,c)),
            'mean_model_record_mean_square_v2':float(np.mean(powers)),
            'mean_square_expected_v2':total,
            'mean_square_standard_error_v2':standard_error,
            'mean_square_z_error':float((np.mean(powers)-total)/standard_error),
            'adc_sndr_computed':False,
        }
    proof={
        'same_pdk_model_version':on['original_model_version']=='4.5' and 'BSIM4v5' in on['original_model_implementation'],
        'intrinsic_time_varying_device_noise':False,
        'switching_sampling_and_comparator_included':False,
        'bandwidth_step_convergence':False,
        'representative_bias_and_pvt_coverage':False,
        'top_level_noise_aware_dynamic_validation':False,
    }
    rc_check={
        'resistance_ohm':R,'capacitance_f':C,'temperature_k':TEMP,
        'analytical_kt_over_c_v2':K*TEMP/C,
        'native_ac_max_complex_relative_error':float(np.max(np.abs(ac['rc_native']/rc_expected-1))),
        'osdi_ac_max_complex_relative_error':float(np.max(np.abs(ac['rc_osdi']/rc_expected-1))),
        'native_psd_max_relative_error_to_4ktr_formula':float(np.max(np.abs(native_psd/theoretical-1))),
        'osdi_psd_max_relative_error_to_4ktr_formula':float(np.max(np.abs(va['amplitude_spectrum']**2/theoretical-1))),
        'native_log_interpolated_known_band_integral_v2':float(expected_continuous),
        'analytical_known_band_integral_v2':float(exact_known),
        'interpolation_and_constant_relative_error':float(abs(expected_continuous/exact_known-1)),
        'osdi_and_native_noise_off_are_zero':all(off['noise'][node]['rms_v']==0 for node in ['rc_native','rc_osdi']),
        'rc_native_and_osdi_transient_noise_on_are_zero':all(on['transient'][node]['std_v']==0 for node in ['rc_native','rc_osdi']),
        'note':'Native and OSDI constants differ slightly; no rescaling is applied.'}
    native_regression={
        'same_model_implementation':on['original_model_implementation'],
        'same_model_version':on['original_model_version'],
        'same_selected_bin':on['original_selected_bin'],
        'same_bias':'W=2um L=1um, VG=.7V, VDD=1.8V, RLOAD=20kohm CLOAD=1pF, 27C',
        'dc_current_relative_error':float(abs(on['op']['vdd#branch']/old_op['vdd#branch']-1)),
        'ac':compare_shared_points(old_ac['frequency'],old_ac['voltage'],ac['frequency'],ac['out']),
        'noise_psd':compare_shared_points(old_noise['frequency'],old_noise['amplitude_spectrum']**2,
                        new_noise['frequency'],new_noise['amplitude_spectrum']**2),
        'noise_1hz_to_100mhz_trapezoid_rms_v':on['noise']['out']['rms_v'],
        'noiseless_transient_std_v':on['transient']['out']['std_v'],
        'time_varying_noise_seed_test':'NOT_APPLICABLE_NO_INTRINSIC_NOISE_REALIZATIONS',
    }
    seed_check={
        'disconnected_software_rng_same_seed_replays':on['disconnected_rng_control']['sha256']==cases['replay_seed11']['disconnected_rng_control']['sha256'],
        'disconnected_software_rng_different_seed_changes':on['disconnected_rng_control']['sha256']!=cases['on_seed29']['disconnected_rng_control']['sha256'],
        'all_native_mos_time_traces_identical':len({case['transient']['out']['uniform_sample_sha256'] for case in cases.values()})==1,
        'interpretation':'The RNG works; no noise source has been inserted into any circuit.'}
    planning_checks={
        'native_rc_ac_matches_analytic':rc_check['native_ac_max_complex_relative_error']<1e-9,
        'native_rc_psd_matches_analytic':rc_check['native_psd_max_relative_error_to_4ktr_formula']<1e-5,
        'native_rc_integral_matches_analytic':rc_check['interpolation_and_constant_relative_error']<1e-4,
        'same_sky130_noise_spectrum_preserved':native_regression['noise_psd']['max_relative_error']<1e-9,
        'same_sky130_ac_preserved':native_regression['ac']['max_relative_error']<1e-9,
        'all_power_conservation_checks':all(s['power_conservation_relative_error']<1e-10 for s in model_stats.values()),
        'all_seed_replay_checks':all(s['rng_same_seed_bit_exact'] and s['rng_different_seed_different_waveform'] for s in model_stats.values()),
        'all_model_mean_square_checks_within_5_standard_errors':all(abs(s['mean_square_z_error'])<5 for s in model_stats.values()),
    }
    result={
        'status':'BLOCKED_NATIVE_INTRINSIC_SWITCHING_NOISE_UNAVAILABLE',
        'planning_method_status':('QUALIFIED_FOR_FINITE_BAND_FROZEN_BIAS_LTI_POWER_ACCOUNTING_ONLY'
            if all(planning_checks.values()) else 'PLANNING_METHOD_CHECK_FAILED'),
        'planning_method_acceptance_checks':planning_checks,
        'cadence_used':False,'new_download_or_install':False,
        'source_results':str(folder.relative_to(HERE)),
        'simulator_runs':run_summary['runs'],
        'actual_run_count':len(run_summary['runs']),
        'physical_run_limit_exhausted':True,
        'all_runs_completed':len(run_summary['runs'])==4 and all(r['run']['returncode']==0 for r in run_summary['runs']),
        'noisetran_rejected_all_runs':all(c['noisetran_rejected_in_log'] for c in cases.values()),
        'native_rc_and_verilog_a_control':rc_check,
        'same_real_sky130_single_device_regression':native_regression,
        'seed_control':seed_check,'planning_models':model_stats,
        'final_noise_qualification_evidence':proof,
        'adc_noise_qualified':qualification_gate(proof),'full_chain_sndr_qualified':False,
        'limitations':[
            'Single fixed bias, not sampled transistor switches or comparator regeneration.',
            'Ordinary .noise is LTI stationary Gaussian analysis, not clocked cyclostationary noise.',
            'Ideal instantaneous sampling is an analytical assumption, not SAR acquisition/hold dynamics.',
            'Unknown power below 1Hz and above 100MHz is not treated as a complete noise budget.',
            'The total stationary PSD retains the selected native model noise calculation, but the finite-record model cannot track switching-dependent multi-node/source correlations, nonlinear noise mixing, clock/reference modulation, or conversion-state memory.',
            'No PDK mismatch Monte Carlo, PVT, complete ADC, or SNDR result is established.',
            'Native NGSPICE BSIM4v5 PSD retained; no VACASK v8 PSD or empirical correction used.'
        ],
        'next_required_capability':'Noise-aware time-domain or periodic-noise engine preserving the actual SKY130 BSIM4v5 implementation and source correlations, followed by multi-bias/device-class and switched-RC controls before any ADC run.',
        'alternative_engine_review':{
            'ngspice_47':'Manual section 11.3.11 still lists generating transient noise from a transistor model among unresolved work; explicit TRNOISE sources are not intrinsic BSIM4 noise.',
            'xyce_7_7_and_7_8':'Official feature tables do not list BSIM4 stationary-noise support (parent primary-document review); this does not establish current 7.10 behavior.',
            'xyce_7_10':'Installed, but no Xyce 7.10 noise circuit was run in this bounded task; NOT_QUALIFIED, no extrapolation from older tables.',
            'vacask':'Installed BSIM4v8 has intrinsic transient-noise capability, but prior actual SKY130 v5 comparison failed noise equivalence; no empirical correction allowed.',
        },
        'primary_sources':[
            {'url':'https://ngspice.sourceforge.io/docs/ngspice-manual.pdf','version':'47, 2026-08-11','sections':['1.2.7','4.1.7','11.3.11','13.5.77']},
            {'url':'https://ngspice.sourceforge.io/osdi.html','claim':'OSDI loads Verilog-A compact models; loading does not establish intrinsic transient noise support.'},
            {'url':'https://ngspice.sourceforge.io/news.html','claim':'Release 47 lists small-signal noise for code models; not a claimed BSIM4 transient-noise implementation.'},
            {'url':'https://xyce.sandia.gov/files/xyce/Xyce_Reference_Guide_7.7.pdf','version':'7.7','review_provenance':'Parent primary-document review; version-limited feature table.'},
            {'url':'https://xyce.sandia.gov/files/xyce/Xyce_Reference_Guide_7.8.pdf','version':'7.8','review_provenance':'Parent primary-document review; subagent fetch timed out, no independent table transcription.'},
        ],
        'evidence_sha256':{str(path.relative_to(HERE)):sha(path) for path in [
            folder/'summary.json',folder/'on_seed11/summary.json',folder/'on_seed11/out_noise.npz',
            folder/'on_seed11/ac.npz',HERE/'probe.py',HERE/'thermal_resistor.va',HERE/'hybrid.py',Path(__file__)]},
    }
    (HERE/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
