#!/usr/bin/env python3
"""Compare genuine tool-version probes without promoting warning counts to PASS."""
import json
from pathlib import Path
import re
import numpy as np
from psf_stream import Trace
from compare_full_adc_stream import digest
from audit_diagnose_log import audit
from audit_saved_comparator import SOURCE

HERE=Path(__file__).resolve().parent
RUNS=HERE.parent/'runs'


def load(path,wanted=None):
    trace=Trace(path,wanted);rows=list(trace.rows())
    names=trace.names if wanted is None else sorted(wanted)
    return trace,np.array([r['time'] for r in rows]),{n:np.array([r[n] for r in rows]) for n in names}


def compare(t,a,u,b,channels):
    if t[0]!=u[0] or t[-1]!=u[-1]:raise ValueError('Version probes must have matching planned stop')
    grid=np.union1d(t,u);out={}
    for label,ns in channels.items():
        v=sum((1 if i==0 else -1)*np.interp(grid,t,a[n]) for i,n in enumerate(ns))
        z=sum((1 if i==0 else -1)*np.interp(grid,u,b[n]) for i,n in enumerate(ns))
        d=z-v;j=np.argmax(abs(d));out[label]={'max_abs_V':float(abs(d[j])),'time_s':float(grid[j]),'new_minus_old_V':float(d[j])}
    return out


def main():
    old=RUNS/'task_20260924T053814697817Z/design';new=RUNS/'task_20260924T055010908278Z/design'
    raw='amsdControl.raw/adc_closure_tran.tran.tran'
    o,t,a=load(old/raw);n,u,b=load(new/raw)
    common=sorted(set(o.names)&set(n.names))
    identity={k:digest(old/k)==digest(new/k) for k in ['amsdControl.scs','reset1_native_bound.scs','sar_controller.v','p1_interfaces.vams','p2_ams_reset1.vams','p2_sequence.sv','profile.vh']}
    if not all(identity.values()):raise ValueError('Unexpected full-probe input difference')
    probe_compare=compare(t,a,u,b,{**{name:(name,) for name in common},'physical_CDAC_TP_minus_TN':('p2_ams_reset1.adc.XADC_TP','p2_ams_reset1.adc.XADC_TN')})
    body_missing=sorted(set(o.names)-set(n.names))
    body={'scope':'Same-input 4.1us first-acquisition tool-bundle probe, not ADC qualification','input_hash_identity':identity,'old_header':o.header,'new_header':n.header,'old_voltage_count':len(o.names),'new_voltage_count':len(n.names),'missing_in_new_waveform':body_missing,'old_points':len(t),'new_points':len(u),'max_same_index_time_difference_s':float(np.max(abs(t-u))) if len(t)==len(u) else None,'common_channel_comparison':probe_compare,'old_log':audit(old/'xrun.log'),'new_log':audit(new/'xrun.log'),'raw_sha256':{'old':digest(old/raw),'new':digest(new/raw)},'interpretation':'25.1 still logs the same int_b LTE relaxation and skips the int_b save. Common external voltages can be compared; no new-tool internal-body waveform is available.'}
    co=RUNS/'task_20260924T021925324213Z';cn=RUNS/'task_20260924T054522930288Z'
    if any(digest(co/f)!=digest(cn/f) for f in ['input.scs','comparator_native_bound.scs']):raise ValueError('Comparator version inputs differ')
    previous=json.loads((SOURCE/'reset1/comparator_fixture/run_strict_001_review.json').read_text())
    wanted={name for c in previous['checks'] for name in c['voltages'] if name!='time'}|{'XCMP.XADC_XCMP_DPOS','XCMP.XADC_XCMP_DNEG','XCMP.XADC_PREP','XCMP.XADC_PREN'}
    oo,tc,ac=load(co/'trace.tran.gz',wanted);nn,uc,bc=load(cn/'trace.tran.gz',wanted)
    checks=[]
    for item in previous['checks']:
        at=item['time_s'];v={k:float(np.interp(at,uc,bc[k])) for k in item['voltages'] if k!='time'}
        logic={k:1 if v[k]>=.7*v['VDD'] else 0 if v[k]<=.3*v['VDD'] else None for k in item['expected']}
        real=None
        if item['kind']=='decision':real=v['XCMP.XADC_XCMP_S_BAR' if item['expected']['Q'] else 'XCMP.XADC_XCMP_R_BAR']<=.3*v['VDD']
        checks.append({'time_s':at,'kind':item['kind'],'pass':logic==item['expected'] and real is not False,'actual_SR_asserted':real,'observed':logic})
    precharge=[]
    for item in previous['precharge_checks']:
        at=item['time_s'];vs={k:float(np.interp(at,uc,bc[k])) for k in ['VDD','XCMP.XADC_XCMP_DPOS','XCMP.XADC_XCMP_DNEG']}
        precharge.append({'time_s':at,'pass':min(vs['XCMP.XADC_XCMP_DPOS'],vs['XCMP.XADC_XCMP_DNEG'])>=.7*vs['VDD']})
    comparisons=compare(tc,ac,uc,bc,{**{k:(k,) for k in wanted},'preamp_differential':('XCMP.XADC_PREP','XCMP.XADC_PREN')})
    newlog=(cn/'spectre.out').read_text();recovery_times=re.findall(r'Newton iteration fails to converge at time = (.*?) step = ([^\n]+)',newlog)
    settled=[]
    for item in previous['checks']:
        at=item['time_s'];d=(np.interp(at,uc,bc['XCMP.XADC_PREP'])-np.interp(at,uc,bc['XCMP.XADC_PREN']))-(np.interp(at,tc,ac['XCMP.XADC_PREP'])-np.interp(at,tc,ac['XCMP.XADC_PREN']))
        settled.append({'time_s':at,'kind':item['kind'],'preamp_differential_new_minus_old_V':float(d)})
    comparator={'scope':'Identical 87-device comparator / stimulus / PDK entry, Spectre-only version change. No physical CDAC/reference ADC gate in fixture.','input_scs_sha256':digest(cn/'input.scs'),'native_sha256':digest(cn/'comparator_native_bound.scs'),'old_header':oo.header,'new_header':nn.header,'old_log':audit(co/'spectre.out'),'new_log':audit(cn/'spectre.out'),'new_Newton_recovery_count':newlog.count('Disaster recovery algorithm is enabled'),'new_Newton_recovery_time_text':recovery_times,'functional_checks':checks,'precharge_checks':precharge,'functional_checks_pass':all(x['pass'] for x in checks+precharge),'real_decision_count':sum(x['kind']=='decision' for x in checks),'selected_all_time_channel_comparison':comparisons,'settled_checks':settled,'raw_compressed_sha256':{'old':digest(co/'trace.tran.gz'),'new':digest(cn/'trace.tran.gz')},'interpretation':'No LTE warning in new comparator does not establish numerical convergence; two Newton recovery events and an AHDL static-matrix warning remain. Version comparison is not same-method precision tightening.'}
    result={'status':'VERSION_PROBE_DIAGNOSTIC_NOT_QUALIFIED','full_ADC_body_probe':body,'isolated_comparator':comparator,'recommended_next':'Restore valid same-primitive int_b/dbnode/sbnode observability under the chosen supported engine using installed help; keep model unchanged. Then a bounded VDS=0 native-buffer/control probe can test the body-network hypothesis. Do not dispatch another long full-ADC run solely because an isolated fixture has no LTE warning.','limits':['Full AMS comparison changes both Xcelium and Spectre bundle; effects cannot be assigned to Spectre alone.','VACOMP portability warnings, skipped save errors and LTE accuracy warnings are different categories.','No PDK/body model/tolerances/acceptance criteria changed.']}
    (HERE/'version25_probe_review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'body_missing':body_missing,'full_common_worst':max(probe_compare.items(),key=lambda kv:kv[1]['max_abs_V']),'comparator_functional_pass':comparator['functional_checks_pass'],'comparator_preamp':comparisons['preamp_differential'],'comparator_selected_worst':max(comparisons.items(),key=lambda kv:kv[1]['max_abs_V']),'comparator_newton_recovery_count':comparator['new_Newton_recovery_count']},indent=2))


if __name__=='__main__':main()
