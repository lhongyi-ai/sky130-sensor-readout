#!/usr/bin/env python3
"""Reproduce this report review; never modify received runs or their statuses.

Independent reference equation transcribed from the public SkyWater model:
https://raw.githubusercontent.com/google/skywater-pdk-libs-sky130_fd_pr/main/cells/res_high_po/sky130_fd_pr__res_high_po_0p35.model.spice
Retrieved 2026-09-12. Constants are source values, not fitted to returned data.
Scope: default nominal process/mismatch coefficients, L=0.35 um, W=0.35 um,
temp=tnom=27 C, the returned 0..0.1 V DC test. No PVT extrapolation.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
RUN=ROOT/'received/runs/res_dc/20260912T092706Z_31ca6c32'
SOURCE='https://raw.githubusercontent.com/google/skywater-pdk-libs-sky130_fd_pr/main/cells/res_high_po/sky130_fd_pr__res_high_po_0p35.model.spice'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())

def reference_resistance(voltage):
    length_um=0.35
    v=abs(voltage)
    shifted=min(v-1.7,0.3)
    end_voltage_scale=(1+(-7.1e-3)*(27-30))/math.sqrt(length_um)
    end=589.99*(1+end_voltage_scale*(-2.02e-2*shifted+1.55e-1*shifted**2+4.61e-2*shifted**3))
    body=(length_um*1112.41)*(1-8.46e-3*v+1.97e-3*v**2+3.30e-5*v**3)
    # Body resistor temperature factor equals one for this run: temp=tnom=27.
    return end+body

def curve(path):
    with path.open() as stream:
        rows=[{key:float(value) for key,value in row.items()} for row in csv.DictReader(stream)]
    if len(rows)!=101: raise ValueError('Expected 101 DC samples')
    if any(not math.isfinite(v) for row in rows for v in row.values()): raise ValueError('Nonfinite data')
    if any(abs(row['x']-index*.001)>1e-12 for index,row in enumerate(rows)):
        raise ValueError('Unexpected DC scan grid')
    if any(abs(row['imag'])>1e-15 for row in rows): raise ValueError('Nonreal DC curve')
    return rows

def main():
    state=read(RUN/'status.json')
    job=state['job']
    if (job['cell'],job['corner'],job['temp'])!=('p1b_tb_res','tt',27):
        raise ValueError('Reference is restricted to this cell and nominal condition')
    fingerprints={name:sha(RUN/name) for name in ['input.scs','native_input.scs','native_netlist.scs','TEST.csv','VTEST_p.csv','spectre.out','ocean_export.log','metrics.json','status.json']}
    checks={
        'package_matches_run':sha(ROOT/'received/package_manifest.json')==state['package_sha256'],
        'package_matches_delivered_runtime_patch':state['package_sha256']==sha(BASE/'runtime_fixes/v1_0_4p1/payload/package_manifest.json'),
        'executed_deck_hash_matches':fingerprints['input.scs']==state['input_sha256'],
        'native_body_hash_matches':fingerprints['native_netlist.scs']==state['native_netlist_sha256'],
        'returned_input_hash_matches':fingerprints['native_input.scs']==read(RUN/'native_selection.json')['returned_input_sha256']}
    sys.path.insert(0,str(BASE/'basic_design'))
    from audit import check
    from analyze import analyze
    check((RUN/'native_netlist.scs').read_text(),read(BASE/'basic_design/design.json'),job['cell'],job['params'])
    checks['native_topology_and_parameters_match']=True
    recomputed=analyze(RUN,job)
    original=read(RUN/'metrics.json')
    checks['old_metrics_reproduced']=all(math.isclose(recomputed[k],original[k],rel_tol=1e-14) for k in ['resistance_ohm','variation_fraction'])
    voltage=curve(RUN/'TEST.csv');current=curve(RUN/'VTEST_p.csv')
    checks['voltage_current_axes_match']=all(a['x']==b['x'] for a,b in zip(voltage,current))
    checks['voltage_matches_stimulus']=all(abs(a['real']-a['x'])<=1e-7 for a in voltage)
    rows=[]
    for a,b in zip(voltage,current):
        v=a['real'];i=-b['real']
        ref_r=reference_resistance(v);ref_i=v/ref_r
        rows.append(dict(voltage_V=v,current_A=i,reference_current_A=ref_i,
                         resistance_ohm=v/i if i else None,reference_resistance_ohm=ref_r,
                         absolute_current_error_A=abs(i-ref_i),
                         relative_current_error=abs(i/ref_i-1) if ref_i else None))
    # Numerical agreement budget: 10 * deck reltol=1e-5, plus 10 * iabstol=1e-13.
    # This is not a relaxed CDF resistance target or a coefficient fit.
    checks['source_equation_matches_all_101_currents']=all(r['absolute_current_error_A']<=1e-12+1e-4*abs(r['reference_current_A']) for r in rows)
    checks['positive_current_for_positive_voltage']=all(r['current_A']>0 for r in rows if r['voltage_V']>0)
    text=(RUN/'spectre.out').read_text()
    completed=re.search(r'spectre completes with (\d+) errors, (\d+) warnings, and (\d+) notices',text,re.I)
    checks['spectre_normal_completion']=bool(completed and completed[1]=='0' and read(RUN/'log_audit.json')['exit_code']==0)
    checks['export_completed']=(RUN/'export_complete.txt').read_text().strip()=='COMPLETE'
    if not all(checks.values()): raise ValueError('Review check failed: '+str(checks))
    with (ROOT/'resistor_recalculated.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    points=[r for r in rows if r['voltage_V']>=.01]
    review=dict(
        run_id=RUN.name,review_status='PASS_DC_MODEL_COMPARISON_AT_REPORTED_CONDITION',
        original_status_preserved=dict(status=state['status'],performance_status=state['performance_status']),
        scope=dict(cell=job['cell'],corner='tt',temperature_C=27,tnom_C=27,length_um=.35,width_um=.35,scan_V=[0,.1,.001]),
        source_url=SOURCE,source_retrieval_date='2026-09-12',reference_script_sha256=sha(Path(__file__)),
        source_coefficients_fitted=False,checks=checks,point_count=101,nonzero_point_count=100,
        max_relative_current_error=max(r['relative_current_error'] for r in rows if r['relative_current_error'] is not None),
        max_absolute_current_error_A=max(r['absolute_current_error_A'] for r in rows),
        original_comparison=dict(mean_resistance_ohm=original['resistance_ohm'],cdf_ohm=979.33,
             nominal_contact_plus_body_ohm=589.99+.35*1112.41,
             difference_percent=100*(original['resistance_ohm']/979.33-1),
             variation_percent=original['variation_fraction']*100,
             minimum_resistance_ohm=min(r['resistance_ohm'] for r in points),
             maximum_resistance_ohm=max(r['resistance_ohm'] for r in points)),
        simulator_summary=dict(errors=int(completed[1]),warnings=int(completed[2]),notices=int(completed[3])),
        examples=[rows[n] for n in [10,50,100]],fingerprints=fingerprints,
        report_sha256=sha(ROOT/'project1_basic_report_20260912T093350Z_ad8b13b5.zip'),
        limitation=['Comparison of returned Spectre CSV with public model equations; no local Cadence execution.',
                    'School model dependency files were not provided or independently hash-matched to upstream.',
                    'Binary PSF is preserved; this review does not independently decode PSF.',
                    'No MIM, RC, OTA, PVT, noise, layout or system qualification follows from this DC result.'],
        next_steps=['Keep the old FAIL result intact; its CDF/linearity criteria were unsuitable for this model.',
                    'Run existing mim_ac and rc_step jobs independently, then return their reports.',
                    'Update passive acceptance together after reviewing capacitor and RC parasitic behavior.'])
    (ROOT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    x=[r['voltage_V']*1000 for r in rows]
    axes[0].plot(x,[r['reference_current_A']*1e6 for r in rows],label='Public model equation',color='#20608a',lw=2)
    axes[0].plot(x[::5],[r['current_A']*1e6 for r in rows[::5]],'o',mfc='none',color='#ba552b',ms=5,label='Spectre CSV')
    axes[0].set(xlabel='Test voltage (mV)',ylabel='Current into resistor (µA)',title='Independent equation agrees with Spectre')
    axes[0].legend(frameon=False)
    axes[1].plot(x[1:],[r['reference_resistance_ohm'] for r in rows[1:]],color='#20608a',lw=2,label='Public model equation')
    axes[1].plot(x[1::5],[r['resistance_ohm'] for r in rows[1::5]],'o',mfc='none',color='#ba552b',ms=5,label='Spectre V / I')
    axes[1].axhline(979.33,color='#777777',ls='--',label='CDF display: 979.33 Ω')
    axes[1].set(xlabel='Test voltage (mV)',ylabel='Resistance (Ω)',title='CDF display omits voltage dependence',ylim=(930,1290))
    axes[1].legend(frameon=False,loc='center right')
    for ax in axes: ax.grid(alpha=.16)
    fig.savefig(ROOT/'resistor_review.png',dpi=180)
    plt.close(fig)
    print(json.dumps({k:review[k] for k in ['review_status','point_count','max_relative_current_error','max_absolute_current_error_A','simulator_summary']},indent=2))

if __name__=='__main__': main()
