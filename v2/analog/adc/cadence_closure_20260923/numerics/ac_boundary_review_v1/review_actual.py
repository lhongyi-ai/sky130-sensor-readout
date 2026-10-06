#!/usr/bin/env python3
"""Audit retained school AC/OP results; no EDA, model edits, or physical pass flag."""
from pathlib import Path
import hashlib, json, math, re, sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLOSURE = HERE.parent.parent
PACKAGE = HERE.parent/'mode_boundary_reproducer_v1/ac_boundary_v1'
RUNS = CLOSURE/'runs/task_20260924T082423953684Z/design/results'
STATIC = HERE.parent/'static_charge_review_v1'
sys.path.insert(0, str(PACKAGE))
from analyze_ac import analyze, read_ac
INSTANCE = 'XTEST.msky130_fd_pr__pfet_01v8'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def struct_fields(path, typename, selected):
    lines = path.read_text().splitlines()
    start = lines.index(f'"{typename}" STRUCT(')+1
    fields = []
    for line in lines[start:]:
        if line == ') PROP(': break
        m = re.match(r'^"([^"]+)" (?:FLOAT|INT) ', line)
        if m: fields.append(m[1])
    start = lines.index(f'"{INSTANCE}" "{typename}" (')+1
    values = []; value_lines = []
    for number, line in enumerate(lines[start:], start+1):
        if line == ') PROP(': end=number; break
        values.append(float(line)); value_lines.append(number)
    assert len(set(fields))==len(fields) and len(fields)==len(values), path
    model = re.fullmatch(r'"model" "([^"]+)"', lines[end]); assert model
    result = {}
    for name in selected:
        if name not in fields:
            result[name]={'status':'NOT_IN_THIS_OUTPUT'}; continue
        i=fields.index(name); value=values[i]
        status='EXPORTED_FINITE_VALUE'
        if not math.isfinite(value): status='NONFINITE_EXPORT_NOT_EFFECTIVE_VALUE'; value=None
        elif value==2147483647: status='INTEGER_SENTINEL_NOT_EFFECTIVE_VALUE'; value=None
        result[name]={'value':value,'raw':lines[value_lines[i]-1],'line_1based':value_lines[i],'status':status}
    return {'file':str(path),'sha256':sha(path),'type_field_count':len(fields),'value_count':len(values),
            'model_attribute':model[1],'model_line_1based':end+1,'fields':result}

def op_nodes(path):
    lines=path.read_text().splitlines(); out={}
    for i in range(lines.index('VALUE')+1, len(lines)):
        line=lines[i]
        m=re.fullmatch(r'"([^"]+)" "(V|I)" ([^\s]+)',line)
        if m:
            assert m[1] not in out
            out[m[1]]={'value':float(m[3]),'unit':m[2],'raw':m[3],'line_1based':i+1}
    assert {'D','G','SB'} <= set(out)
    assert all(math.isfinite(v['value']) for v in out.values())
    return out

def last_place_half(token):
    # Budget from actual text precision, not a physical acceptance tolerance.
    parts=re.fullmatch(r'[-+]?(\d+)(?:\.(\d*))?(?:[eE]([-+]?\d+))?',token)
    if not parts: raise ValueError(token)
    return 0.5*10**(int(parts[3] or 0)-len(parts[2] or ''))

def raw_current_printing_audit(path):
    rows=[]; row=None
    for line in path.read_text().split('\nVALUE\n',1)[1].splitlines():
        if line=='END': break
        m=re.fullmatch(r'"([^"]+)" (.+)',line); assert m
        if m[1]=='freq':
            if row is not None: rows.append(row)
            row={'freq':float(m[2])}; continue
        z=re.fullmatch(r'\(([^\s]+) ([^\s]+)\)',m[2]); assert z
        row[m[1]]=(float(z[1]),float(z[2]),last_place_half(z[1]),last_place_half(z[2]))
    if row is not None: rows.append(row)
    source=['VD:p','VG:p','VS:p']; checks=[]
    for row in rows:
        residual=[sum(row[n][c] for n in source) for c in [0,1]]
        budget=[sum(row[n][c+2] for n in source) for c in [0,1]]
        # Device/source equality for SB requires addition of two separately printed terminals.
        sb=[-row['VS:p'][c]-row[INSTANCE+':s'][c]-row[INSTANCE+':b'][c] for c in [0,1]]
        sb_budget=[row['VS:p'][c+2]+row[INSTANCE+':s'][c+2]+row[INSTANCE+':b'][c+2] for c in [0,1]]
        checks.append({'frequency_Hz':row['freq'],'sum_source_currents_A':residual,'sum_half_last_printed_place_A':budget,
                       'abs_residual_over_printing_budget':[abs(x)/b for x,b in zip(residual,budget)],
                       'SB_source_minus_s_plus_b_A':sb,'SB_sum_half_last_printed_place_A':sb_budget,
                       'SB_abs_residual_over_printing_budget':[abs(x)/b for x,b in zip(sb,sb_budget)]})
    return {'rows':checks,'max_KCL_component_over_printing_budget':max(v for x in checks for v in x['abs_residual_over_printing_budget']),
            'max_SB_component_over_printing_budget':max(v for x in checks for v in x['SB_abs_residual_over_printing_budget']),
            'interpretation':'Residuals and text-rounding budgets only; no independent exact charge/current conservation proof.'}

def main():
    frozen=json.loads((PACKAGE/'manifest.json').read_text())
    static_branch=json.loads((STATIC/'branch_analysis.json').read_text())
    static_meta=json.loads((STATIC/'metadata_review.json').read_text())['profiles']['strict']['file_literal_metadata']
    cases={}
    for name, expected in frozen['cases'].items():
        dirs=list(RUNS.glob(name+'_*')); assert len(dirs)==1
        run=dirs[0]; result=analyze(run)
        assert sha(run/'package_manifest.json')==sha(PACKAGE/'manifest.json')
        assert result['case']==name and result['log_completion']==['spectre completes with 0 errors, 0 warnings, and 1 notice.']
        raw=run/'input.raw'; nodes=op_nodes(raw/'acBoundary.info')
        actual_delta=nodes['D']['value']-nodes['SB']['value']
        op=struct_fields(raw/'acBoundary.info','bsim4',['reversed','region','vgs','vds','vbs','vgd','vdb','vgb','ids','gm','gds','gmbs','cgd','cdd','cbd','cgdbo','cddbo','cbdbo','qg','qd','qs','qb'])
        element=struct_fields(raw/'element.info','bsim4~instparams',['w','l','m','nf','rbodymod','rgatemod','trnqsmod','acnqsmod','rbpb','rbpd','rbps','rbdb','rbsb'])
        output=struct_fields(raw/'outputParameter.info','bsim4~instparams',['tempeff','meff','weff','leff','weffcv','leffcv'])
        assert {op['model_attribute'],element['model_attribute'],output['model_attribute']}=={'XTEST.sky130_fd_pr__pfet_01v8__model.8'}
        assert nodes['G']['value']==frozen['gate_dc_V'] and nodes['SB']['value']==frozen['source_body_dc_V']
        assert abs(actual_delta-expected['delta_D_minus_SB_V'])<1e-14 # DC output round-trip only.
        assert op['fields']['reversed']['value']==(0 if actual_delta<0 else 1)
        assert element['fields']['w']['value']==32e-6 and element['fields']['l']['value']==150e-9
        assert element['fields']['m']['value']==1 and element['fields']['nf']['value']==1
        meta=json.loads((run/'model_metadata_before.json').read_text()); assert meta==static_meta
        schema,rows=read_ac(raw/'acBoundary.ac')
        assert len(schema)==13
        assert all(row['D']==1+0j and row['G']==0j and row['SB']==0j for row in rows)
        ports={}
        for port in ['D','G','SB']:
            vals=[r['ports'][port] for r in result['rows']]
            cs=[v['C_effective_kD_F'] for v in vals]; gs=[v['G_kD_S'] for v in vals]
            ports[port]={'low_frequency_Ceff_F':cs[0],'high_frequency_Ceff_F':cs[-1],'min_Ceff_F':min(cs),'max_Ceff_F':max(cs),'span_Ceff_F':max(cs)-min(cs),
                         'low_frequency_G_S':gs[0],'high_frequency_G_S':gs[-1],'min_G_S':min(gs),'max_G_S':max(gs)}
        printing=raw_current_printing_audit(raw/'acBoundary.ac')
        result['OP_bias_and_reversed_review']='ACTUAL_DC_NODES_AND_OP_REVIEWED_IN_SUMMARY'
        result['OP_review_reference']='summary.json / cases / '+name
        (HERE/(name+'_external_response.json')).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        case={'run':str(run),'requested_delta_V':expected['delta_D_minus_SB_V'],'actual_delta_V':actual_delta,'delta_error_V':actual_delta-expected['delta_D_minus_SB_V'],
              'actual_DC_nodes':nodes,'operating_point':op,'instance':element,'output_parameters':output,'actual_AC_trace_schema':schema,
              'AC_drive_verified':{'D': [1,0],'G':[0,0],'SB':[0,0]},'actual_frequency_points':len(rows),'ports':ports,
              'model_file_metadata_same_as_static_strict':True,'input_manifest_hash_verified':True,'exit_error_warning_notice':[0,0,0,1],
              'printing_audit':printing,'max_external_KCL_relative_residual':max(r['KCL_residual_fraction_of_sum_magnitudes'] for r in result['rows']),
              'max_external_KCL_abs_A':max(math.hypot(*r['KCL_sum_external_device_currents_A']) for r in result['rows']),
              'direct_device_current_crosscheck_max_residual_A':{p:max(math.hypot(*r['source_vs_direct_device_current_residual_A'][p]) for r in result['rows']) for p in ['D','G','SB']},
              'lowfreq_gate_Ceff_minus_OP_cgd_F':ports['G']['low_frequency_Ceff_F']-op['fields']['cgd']['value'],
              'raw_sha256':{p.name:sha(p) for p in [run/'input.scs',run/'package_manifest.json',run/'spectre.out',run/'model_metadata_before.json',raw/'acBoundary.ac',raw/'acBoundary.info',raw/'element.info',raw/'outputParameter.info']}}
        cases[name]=case
    step={p:cases['dp1u']['ports'][p]['low_frequency_Ceff_F']-cases['dn1u']['ports'][p]['low_frequency_Ceff_F'] for p in ['D','G','SB']}
    fits=static_branch['fits']['strict_up']
    raw_delta={q:fits[q][0]['positive_minus_negative_slope_F'] for q in ['qgi','qdi','qsi','qbi']}
    result={'status':'ACTUAL_EXTERNAL_AC_BRANCH_RESPONSE_OBSERVED_NOT_MODEL_FAULT_OR_ADC_PASS','cases':cases,
            'external_AC_1kHz_positive1u_minus_negative1u_Ceff_F':step,
            'static_raw_Q_strict_1to5u_fit_positive_minus_negative_slopes_F':raw_delta,
            'comparison_scope':'Different observables and finite-bias/windows; same-direction branch differences do not establish equal charge definitions or uniquely identify an implementation/model fault.',
            'evidence':{'frozen_manifest_sha256':sha(PACKAGE/'manifest.json'),'frozen_analyzer_sha256':sha(PACKAGE/'analyze_ac.py'),
                        'static_branch_sha256':sha(STATIC/'branch_analysis.json'),'static_metadata_sha256':sha(STATIC/'metadata_review.json'),'review_script_sha256':sha(Path(__file__))},
            'formal_ADC_PEX_allowed':False,'complete_ADC':False,'full_ADC_accuracy_pass':False,'transient_LTE_repair_proven':False}
    (HERE/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(result['status'])
    for name,c in cases.items():
        print(name,'actual_D-S_uV',c['actual_delta_V']*1e6,'reversed',c['operating_point']['fields']['reversed']['value'],'Ceff_D_G_SB_fF',[c['ports'][p]['low_frequency_Ceff_F']*1e15 for p in ['D','G','SB']])
    print('maxprintbudget_KCL',max(c['printing_audit']['max_KCL_component_over_printing_budget'] for c in cases.values()))
    print('maxprintbudget_SB',max(c['printing_audit']['max_SB_component_over_printing_budget'] for c in cases.values()))

if __name__=='__main__': main()
