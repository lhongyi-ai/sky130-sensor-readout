#!/usr/bin/env python3
"""Independent actual AC port and printed-number audit; no EDA execution."""
from pathlib import Path
from decimal import Decimal
import cmath
import hashlib
import json
import math
import re

HERE = Path(__file__).resolve().parent
CLOSURE = HERE.parent.parent
RUNS = CLOSURE / 'runs/task_20260924T082423953684Z/design/results'
P = 'XTEST.msky130_fd_pr__pfet_01v8:'
REQUIRED = {'D', 'G', 'SB', 'VD:p', 'VG:p', 'VS:p', *[P+x for x in ['d','g','s','b','dbnode','sbnode','int_b']]}


def half_quantum(token):
    """Half of the last shown decimal place, not a solver-error bound."""
    return float(Decimal(5).scaleb(Decimal(token).as_tuple().exponent - 1))


def parse(path):
    before, content = path.read_text().split('\nVALUE\n', 1)
    assert '"analysis type" "ac"' in before
    rows = []
    row = None
    for line in content.splitlines():
        if line == 'END' or not line.strip():
            continue
        m = re.fullmatch(r'"freq" ([+\-0-9.eE]+)', line)
        if m:
            if row is not None:
                rows.append(row)
            row = {'freq': float(m[1]), 'values': {}, 'rounding': {}}
            continue
        m = re.fullmatch(r'"([^"]+)" \(([^\s]+) ([^\s]+)\)', line)
        if m is None or row is None:
            raise ValueError('Unsupported actual AC record: ' + line)
        n, rs, ims = m.groups()
        assert n not in row['values']
        z = complex(float(rs), float(ims))
        assert math.isfinite(z.real) and math.isfinite(z.imag)
        row['values'][n] = z
        row['rounding'][n] = [half_quantum(rs), half_quantum(ims)]
    if row is not None:
        rows.append(row)
    assert len(rows) == 41
    for i, r in enumerate(rows):
        assert set(r['values']) == REQUIRED
        assert math.isclose(r['freq'], 1000*10**(i/10), rel_tol=1e-12)
    return rows


def signed_sum(row, terms):
    z = sum(factor*row['values'][name] for factor, name in terms)
    quant = [sum(abs(factor)*row['rounding'][name][j] for factor, name in terms) for j in [0,1]]
    return {'residual_A': [z.real,z.imag], 'printed_half_quantum_sum_A': quant,
            'residual_within_printed_rounding_bound': all(abs(v) <= q for v,q in zip([z.real,z.imag],quant))}


def review(run):
    case = (run/'case.txt').read_text().strip()
    manifest = json.loads((run/'package_manifest.json').read_text())
    assert hashlib.sha256((run/'input.scs').read_bytes()).hexdigest() == manifest['cases'][case]['sha256']
    assert int((run/'exit_code.txt').read_text()) == 0
    assert int((run/'model_hash_comparison_exit.txt').read_text()) == 0
    assert (run/'model_metadata_before.json').read_bytes() == (run/'model_metadata_after.json').read_bytes()
    log = (run/'spectre.out').read_text()
    completion = re.findall(r'spectre completes with [^\n]+', log)
    rows = parse(run/'input.raw/acBoundary.ac')
    out = []
    for row in rows:
        v = row['values']; f=row['freq']; w=2*math.pi*f
        assert v['D'] == 1+0j and v['G'] == 0j and v['SB'] == 0j
        y = {k: -v[n]/v['D'] for k,n in [('D','VD:p'),('G','VG:p'),('SB','VS:p')]}
        # These are measured linearized external currents, not raw Q finite differences.
        ys = {k:{'Y_S':[z.real,z.imag], 'phase_deg':math.degrees(cmath.phase(z)), 'ImY_over_omega_F':z.imag/w} for k,z in y.items()}
        kcl = signed_sum(row, [(-1,n) for n in ['VD:p','VG:p','VS:p']])
        direct = {k:signed_sum(row, terms) for k,terms in {
            'D':[(-1,'VD:p'),(-1,P+'d')],
            'G':[(-1,'VG:p'),(-1,P+'g')],
            'SB':[(-1,'VS:p'),(-1,P+'s'),(-1,P+'b')],
        }.items()}
        out.append({'frequency_Hz':f, 'Y_column':ys, 'external_current_KCL':kcl,
                    'source_vs_direct_terminal_currents':direct,
                    'internal_body_voltage_magnitude_per_unit_D':{n:abs(v[P+n]) for n in ['dbnode','sbnode','int_b']}})
    summary = {k:{'Ceff_range_F':[min(r['Y_column'][k]['ImY_over_omega_F'] for r in out),max(r['Y_column'][k]['ImY_over_omega_F'] for r in out)],
                  'phase_range_deg':[min(r['Y_column'][k]['phase_deg'] for r in out),max(r['Y_column'][k]['phase_deg'] for r in out)]} for k in ['D','G','SB']}
    return {'case':case,'run':str(run),'raw_sha256':hashlib.sha256((run/'input.raw/acBoundary.ac').read_bytes()).hexdigest(),'input_sha256':manifest['cases'][case]['sha256'],
            'requested_delta_D_minus_SB_V':manifest['cases'][case]['delta_D_minus_SB_V'], 'log_completion':completion, 'fields': sorted(REQUIRED),
            'point_count':len(rows),'actual_excitation_D_G_SB_V':[[1,0],[0,0],[0,0]],'summary':summary,'rows':out}


def main():
    results = {}
    for run in sorted(RUNS.iterdir()):
        if run.is_dir():
            r = review(run); results[r['case']] = r
    assert set(results) == {'dn20u','dn5u','dn1u','d0','dp1u','dp5u','dp20u'}
    diffs=[]
    for a,b in zip(results['dn1u']['rows'],results['dp1u']['rows']):
        assert a['frequency_Hz'] == b['frequency_Hz']
        diffs.append({'frequency_Hz':a['frequency_Hz'],'positive_minus_negative_Ceff_F':{k:b['Y_column'][k]['ImY_over_omega_F']-a['Y_column'][k]['ImY_over_omega_F'] for k in ['D','G','SB']}})
    dc=json.loads((HERE.parent/'static_charge_review_v1/branch_analysis.json').read_text())
    juxtapose={}
    for port,q in [('D','qdi'),('G','qgi')]:
        a=dc['fits']['strict_up'][q][0]
        juxtapose[port]={'AC_negative_1uV_1kHz_Ceff_F':results['dn1u']['rows'][0]['Y_column'][port]['ImY_over_omega_F'],
                        'AC_positive_1uV_1kHz_Ceff_F':results['dp1u']['rows'][0]['Y_column'][port]['ImY_over_omega_F'],
                        'DC_raw_charge_field':q,'DC_negative_1_to_5uV_signed_slope_F':a['negative']['slope_dQ_dExternalD_F'],
                        'DC_positive_1_to_5uV_signed_slope_F':a['positive']['slope_dQ_dExternalD_F'],
                        'AC_positive_minus_negative_Ceff_F':diffs[0]['positive_minus_negative_Ceff_F'][port],
                        'DC_positive_minus_negative_slope_F':a['positive_minus_negative_slope_F']}
    out={'status':'INDEPENDENT_EXTERNAL_AC_PORT_AUDIT_ONLY','cases':results,'mode_branch_differences':diffs,'AC_DC_scope_limited_juxtaposition':juxtapose,
         'limits':['AC unit drive is linearized normalization, not a 1 V finite-amplitude transient.',
                   'I_device enters the three external D/G/SB ports; device S and B remain joined.',
                   'Printed complex currents have roughly six significant digits. Rounding intervals describe serialization only, not physical or solver error.',
                   'Ceff is signed Im(Y)/omega for fixed G/SB; not automatically intrinsic capacitance or full capacitance matrix.',
                   'Raw DC charge aliases do not uniquely specify overlap/junction decomposition. The branch contrast is corroborated by terminal response, but not sufficient to declare a model or solver defect.',
                   'Only seven discrete DC biases and one external Y column tested; no mathematical one-sided limit, four-terminal body separation, transient integration or ADC qualification is established.'],
         'complete_ADC':False,'full_ADC_accuracy_pass':False}
    (HERE/'review.json').write_text(json.dumps(out,indent=2)+'\n')
    for case,r in results.items():
        print(case, 'Ceff_1kHz_fF', {k:r['rows'][0]['Y_column'][k]['ImY_over_omega_F']*1e15 for k in ['D','G','SB']})
    kcls=[r['external_current_KCL'] for c in results.values() for r in c['rows']]
    direct=[v for c in results.values() for r in c['rows'] for v in r['source_vs_direct_terminal_currents'].values()]
    print('KCL printed interval contains zero',sum(x['residual_within_printed_rounding_bound'] for x in kcls),len(kcls))
    print('Direct comparison printed interval contains zero',sum(x['residual_within_printed_rounding_bound'] for x in direct),len(direct))


if __name__=='__main__':main()
