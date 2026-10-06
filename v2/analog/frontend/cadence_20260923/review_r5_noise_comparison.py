#!/usr/bin/env python3
"""Independent r4-to-r5 actual noise/OP/AC comparison and bounded sensitivities."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np
from parse_noise_psf import parse_noise, integrate_psd
from review_three_gain import MOS, parse_spectre_psf_ascii
from review_temperature_screen import decompose, gain_model
from audit_native_netlist import parse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROOT = REPO/'v2/cadence/linuxlab_20260923/runs'
NOISE = {'r4': ROOT/'spectre_noise_screen_20260923T112542186497Z',
         'r5': ROOT/'spectre_noise_screen_20260923T112728045435Z'}
STATIC = {'r4': ROOT/'spectre_three_gain_20260923T110840899589Z',
          'r5': ROOT/'spectre_three_gain_20260923T112630358378Z'}
BANDS = {'1Hz_50kHz': (1., 5e4), 'one_fft_bin_50kHz': (1e5/16384, 5e4),
         '1Hz_100MHz': (1., 1e8)}
HASHES = {}


def track(p):
    HASHES[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p.read_text()


def read(p):
    track(p); r = parse_spectre_psf_ascii(p)
    assert r.status.value == 'success'
    return r.data


def group(n):
    if n in ['RSP', 'RSN']: return 'sensor_source_350ohm'
    if n.startswith('XPGA_XRIN'): return 'input_PDK_resistors'
    if re.match(r'XPGA_XF[PN](1|4|16)_XR', n): return 'feedback_PDK_resistors'
    if re.match(r'XPGA_XF[PN](1|4|16)_XSW', n): return 'feedback_TG_MOS'
    if any(n.startswith('XPGA_XOTA_'+s+'.') for s in ['XMIP','XMIN']): return 'input_pair_MOS'
    if any(n.startswith('XPGA_XOTA_'+s+'.') for s in ['XMLP','XMLN']): return 'first_stage_P_load_MOS'
    if any(n.startswith('XPGA_XOTA_'+s+'.') for s in ['XMOP','XMON','XMSP','XMSN']): return 'second_stage_MOS'
    if n.startswith('XPGA_XOTA_XRN'): return 'first_stage_CM_RN_resistors'
    if any(n.startswith('XPGA_XOTA_'+s) for s in ['XRCM','XRDS','XRSC']): return 'other_CM_resistors'
    if n.startswith('XPGA_XOTA_XRZ'): return 'compensation_resistors'
    if n.startswith('XPGA_XOTA_XBIAS_XR'): return 'bias_resistors'
    if n.startswith(('XRIP_XR.','XRIN_XR.')): return 'output_isolation_resistors'
    if n.startswith(('XTGP_','XTGN_')): return 'proxy_sampling_MOS'
    return 'other_devices'


def noise_summary(run):
    output = {}
    for gain in [1,4,16]:
        for stage in ['front','track']:
            d = parse_noise(track(run/'input.raw'/('g{}_{}.noise'.format(gain,stage))))
            f = d['frequency']; assert len(f)==401 and f[0]==1 and f[-1]==1e8
            entry = {}
            for label,(lo,hi) in BANDS.items():
                I = lambda v: integrate_psd(f,v,lo,hi)
                total = I(d['out_asd']**2); groups = {}; mechanisms = {}; sources = {}
                for n,z in d['devices'].items():
                    p = I(z['total']); sources[n] = p
                    category = group(n); gg = groups.setdefault(category, {'variance_v2': 0., 'mechanisms_v2': {}})
                    gg['variance_v2'] += p
                    for k,v in z.items():
                        if k == 'total': continue
                        p = I(v); mechanisms[k] = mechanisms.get(k,0.)+p
                        gg['mechanisms_v2'][k] = gg['mechanisms_v2'].get(k,0.)+p
                assert abs(sum(sources.values())/total-1)<1e-10
                for z in groups.values(): z['percent_variance'] = 100*z['variance_v2']/total
                entry[label] = {'variance_v2': total, 'rms_v': total**.5,
                    'grouped_sources': groups, 'mechanisms_variance_v2': mechanisms,
                    'mechanisms_percent': {k:100*v/total for k,v in mechanisms.items()},
                    'top20_sources': [{'name':n,'variance_v2':v,'percent_variance':100*v/total}
                                      for n,v in sorted(sources.items(),key=lambda a:a[1],reverse=True)[:20]]}
            output['g{}_{}'.format(gain,stage)] = entry
    return output


def ac_summary(d, gain):
    f = np.array(d['freq']); mag = abs((np.array(d['FP'])-d['FN'])/(np.array(d['VINP'])-d['VINN']))
    db = 20*np.log10(mag/mag[0]); cross=[]
    for k in range(len(f)-1):
        if (db[k]+3)*(db[k+1]+3)<0:
            t=(-3-db[k])/(db[k+1]-db[k]); cross.append(float(np.exp(np.log(f[k])+t*np.log(f[k+1]/f[k]))))
    return {'gain_1hz': float(mag[0]), 'peak_above_1hz_db': float(max(db)),
            'all_minus3db_crossings_hz_log_interpolated': cross,
            'one_hz_decomposition': decompose(d,gain),
            'scope': 'Closed-loop differential AC only. No phase-margin or coupled-stability claim.'}


def main():
    path=HERE/'r5_noise_vs_r4_independent_review.json'
    if path.exists(): raise SystemExit('Preserve existing result; use a new output version.')
    for name in ['review_r5_noise_comparison.py','parse_noise_psf.py','review_three_gain.py','review_temperature_screen.py']:
        track(HERE/name)
    spec=json.loads(track(REPO/'v2/config/spec.json'))
    results={}; static={}; logs={}; noise_native={}
    for revision,run in NOISE.items():
        native=track(run/'native_netlist');noise_native[revision]=parse(native)[0]
        assert track(STATIC[revision]/'native_netlist') == native
        assert 'dc_pivot_check=yes' in track(run/'input.scs')
        results[revision]=noise_summary(run)
        info=read(run/'input.raw/dcOpInfo.info')
        mos={}
        for dev in MOS:
            stem='XPGA_XOTA_'+dev+'.msky130_fd_pr__'+('pfet_01v8' if dev in ['XMLN','XMLP','XMSN','XMSP'] else 'nfet_01v8')
            mos[dev]={k:info[stem+':'+k] for k in ['id','gm','gds','vgs','vds','vdsat','vth','cgg']}
            assert all(np.isfinite(v) for v in mos[dev].values())
        static[revision]={'gain4_initial_MOS_OP':mos,'gains':{}}
        review=json.loads(track(HERE/('three_gain_r4_independent_review.json' if revision=='r4' else 'three_gain_r5_noise_independent_review.json')))
        for g in [1,4,16]:
            op=read(STATIC[revision]/'input.raw'/('g{}_op.dc'.format(g)))
            ac=read(STATIC[revision]/'input.raw'/('g{}_ac.ac'.format(g)))
            z=review['gains'][str(g)]
            static[revision]['gains'][str(g)]={'zero_common_mode_v':(op['FP']+op['FN'])/2,
                'zero_frontend_vdd_plus_vcm_power_w':-op['VDD_SRC:p']*1.8-op['VCM:p']*.9,
                'common_mode_over81':z['output_common_mode_v'],
                'output_diff_over81':z['output_differential_v'],
                'out_of_adc_range_count':z['adc_differential_range_exceeded']['count'],
                'analog_calibration_78holdout_lsb':z['calibration']['max_independent_residual_lsb'],
                'all13_region2_all81':z['all_13_mos_saturated_region2_at_81_points'],
                'smallest_core_saturation_margin_v':min(v['min_abs_vds_minus_abs_vdsat_v'] for v in z['core_mos'].values()),
                'ac':ac_summary(ac,g)}
        for p in [run,STATIC[revision]]:
            s=track(p/'spectre.out');track(p/'completion.json');track(p/'provenance.json');track(p/'input.scs')
            counts=re.search(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?\.',s)
            assert counts.group(1)=='0'
            logs[p.name]={'errors_warnings_notices':[int(v) for v in counts.groups()],
                'bad_pivot_notice':'Bad pivoting' in s,'gmin_notice_count':s.count('GminDC ='),
                'warning_codes':re.findall(r'WARNING \(([^)]+)\)',s)}
    changes={}
    for n,z in noise_native['r4'].items():
        if z != noise_native['r5'][n]: changes[n]={k:{'before':z[k],'after':noise_native['r5'][n][k]} for k in ['nodes','model','parameters'] if z[k]!=noise_native['r5'][n][k]}
    assert set(changes)=={'XPGA_XOTA_XMIP','XPGA_XOTA_XMIN','XPGA_XOTA_XMLP','XPGA_XOTA_XMLN'}
    for z in changes.values(): assert set(z)=={'parameters'}
    comparisons={}
    for label in BANDS:
        a=results['r4']['g16_track'][label];b=results['r5']['g16_track'][label]
        selected=lambda z,n:z['grouped_sources'][n]['mechanisms_v2']['fn']
        fn_i=selected(a,'input_pair_MOS');fn_l=selected(a,'first_stage_P_load_MOS')
        prediction=a['variance_v2']-fn_i-fn_l+fn_i/16+fn_l/4
        comparisons[label]={'before_rms_v':a['rms_v'],'after_rms_v':b['rms_v'],
            'rms_reduction_db':20*np.log10(a['rms_v']/b['rms_v']),
            'input_pair_actual_fn_power_ratio':selected(b,'input_pair_MOS')/fn_i,
            'load_pair_actual_fn_power_ratio':selected(b,'first_stage_P_load_MOS')/fn_l,
            'conditional_prior_prediction_rms_v':prediction**.5,
            'actual_over_prediction_rms_ratio':b['rms_v']/prediction**.5}
    # A deliberately limited resistor sensitivity: scale input R by k, retune
    # feedback R at nominal to retain the same small-signal gain. Use measured
    # r4 TT temperature impedances, not fabricated r5 temperature measurements.
    r4temps={27:STATIC['r4'],-20:ROOT/'spectre_three_gain_20260923T110850521882Z',
             85:ROOT/'spectre_three_gain_20260923T110859261509Z'}
    temp={t:decompose(read(p/'input.raw/g1_ac.ac'),1) for t,p in r4temps.items()}
    sensitivities={}
    nom=temp[27];ri0,rf0,ron0,A0=[nom[k]['real'] for k in ['Rin_ohm','Rfb_ohm','Ron_ohm','A_core']]
    original_gain=gain_model(ri0,rf0,ron0,A0)
    targetK=original_gain*(A0+1)/(A0-original_gain)
    for scale in [1.,.5,.25]:
        rf_nom=targetK*(ri0*scale+350)-ron0; rf_ratio=rf_nom/rf0
        values={}
        for t,d in temp.items():
            ri,rf,ron,A=[d[k]['real'] for k in ['Rin_ohm','Rfb_ohm','Ron_ohm','A_core']]
            gain=gain_model(ri*scale,rf*rf_ratio,ron,A)
            values[str(t)]={'conditional_gain':gain,'fixed_nominal_endpoint_gain_term_lsb':2048*(gain/original_gain-1),
                'ron_fraction_feedback':ron/(rf*rf_ratio+ron),'source350_fraction_input':350/(ri*scale+350)}
        i=.2/(ri0*scale+350)
        sensitivities[str(scale)]={'input_resistance_scale':scale,'feedback_nominal_scale':rf_ratio,
            'assumed_constant_A_and_Ron_per_temperature':True,'temperatures':values,
            'g1_full_scale_differential_signal_current_per_feedback_leg_a':i,
            'two_input_and_feedback_resistors_signal_dissipation_w':2*i*i*(ri0*scale+rf_nom),
            'scope':'Counterfactual r4 linear small-signal sensitivity, not r5 PVT, actual full-scale transistor current or validated design. Source350 stays fixed. Resistor temperature ratio extrapolated unchanged despite geometry changes; internal gain/bandwidth/CM/loading frozen.'}
    report={'status':'REAL_R5_AREA_EXPERIMENT_ANALYZED_NOT_QUALIFIED',
        'native_changed_instances_exactly_four':changes,'noise':results,'static':static,
        'g16_comparison':comparisons,'r4_based_resistor_tradeoff_NOT_SIMULATED':sensitivities,
        'logs':logs,'spec_unchanged':True,
        'limitations':['Fixed acquisition proxy; no time-varying sampled noise transfer or actual bottom-plate ADC.',
            'New r5 has no measured temperature/PVT, coupled-stability or transient-settling evidence in this review.',
            'The r4 solver control establishes identical saved values, not general immunity to numerical or model errors.',
            'Each revision uses its own nominal calibration for curvature only; that is not a cross-temperature recalibration.'],
        'hashes':HASHES}
    path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'g16':comparisons,'static':{r:{g:{k:v for k,v in x.items() if k!='ac'} for g,x in s['gains'].items()} for r,s in static.items()},'R_sensitivity':sensitivities},indent=2))


if __name__=='__main__':main()
