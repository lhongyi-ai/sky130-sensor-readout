#!/usr/bin/env python3
"""Audit existing releases, pin exact views, and prepare a partial RC connection fixture."""
import hashlib, json, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads((ROOT / path).read_text())

def spice_lines(path):
    lines=[]
    for raw in path.read_text().splitlines():
        line=raw.strip()
        if line.startswith('+') and lines: lines[-1] += ' '+line[1:].strip()
        elif line and not line.startswith('*'): lines.append(line)
    return lines

def subckt(path, name):
    lines=spice_lines(path)
    for line in lines:
        t=line.split()
        if len(t)>1 and t[0].lower()=='.subckt' and t[1].lower()==name.lower():
            pins=[]
            for x in t[2:]:
                if '=' in x or x.lower()=='params:': break
                pins.append(x)
            return pins
    raise ValueError('missing subcircuit '+name)

def rc_counts(path):
    c={'resistors':0,'capacitors':0,'positive_resistors':0,'positive_capacitors':0,'mim_devices':0}
    for line in spice_lines(path):
        t=line.split()
        if t[0][0].upper() in ('R','C'):
            kind='resistors' if t[0][0].upper()=='R' else 'capacitors';c[kind]+=1
            m=re.match(r'([+\-]?[0-9.]+(?:[eE][+\-]?[0-9]+)?)',t[3])
            if m and float(m.group(1))>0:c['positive_'+kind]+=1
        if t[0][0].upper()=='X' and 'sky130_fd_pr__cap_mim_m3_1' in t:c['mim_devices']+=1
    return c

def main():
    digital='v2/physical/digital'; switch='v2/physical/adc_switch';cdac='v2/physical/cdac_route_20260911'
    d=read(digital+'/results/physical_validation.json');s=read(switch+'/results/sampling_switch_release.json');c=read(cdac+'/qualification.json')
    checks=[]; omitted_intermediates=[]
    def check(name,ok,detail=None):checks.append({'check':name,'passed':bool(ok),'detail':detail})
    hashes={}
    def audit_hashes(base, values, portable_only=False):
        for rel, expected in values.items():
            p=ROOT/base/rel
            key=p.relative_to(ROOT).as_posix()
            if portable_only and not p.is_file():
                omitted_intermediates.append(key);continue
            ok=p.is_file() and sha(p)==expected
            check('release_sha256:'+key,ok)
            hashes[key]=expected
    audit_hashes('',d['source_sha256']);audit_hashes('',d['artifact_sha256'])
    audit_hashes(cdac,c['key_artifact_sha256'])
    sv=read(switch+'/artifacts/dummy_layout_final/validation.json')
    audit_hashes('',sv['source_sha256']);audit_hashes(switch+'/artifacts/dummy_layout_final',sv['artifact_sha256'], portable_only=True)
    audit_hashes(switch,{s['frozen_interface']['schematic_file']:s['candidate_sha256'],s['frozen_interface']['rc_file']:s['rc_sha256'],s['frozen_interface']['gds_file']:s['gds_sha256']})
    for name,report,want in [('digital',d,'passed'),('sampling_switch',s,'STANDALONE_SAMPLING_SWITCH_QUALIFIED'),('cdac',c,'SKY130_CDAC_ROUTED_OPEN_PDK_PASS')]:
        check(name+':release_status',report['status']==want)
        check(name+':release_checks',all(x.get('passed',False) if isinstance(x,dict) else x is True for x in report['checks'].values()))
    check('digital:raw_lvs_unique','Circuits match uniquely' in (ROOT/digital/'evidence/71-netgen-lvs/reports/lvs.netgen.rpt').read_text())
    check('digital:raw_drc_zero','[INFO] COUNT: 0' in (ROOT/digital/'evidence/65-magic-drc/reports/drc.magic.rpt').read_text())
    check('switch:raw_lvs_unique','Circuits match uniquely' in (ROOT/switch/'artifacts/dummy_layout_final/lvs.rpt').read_text())
    check('switch:raw_drc_zero','TG_DRC_COUNT 0' in (ROOT/switch/'artifacts/dummy_layout_final/layout.log').read_text())
    check('cdac:raw_lvs_unique','Circuits match uniquely' in (ROOT/cdac/'artifacts/top_lvs.rpt').read_text())
    check('cdac:raw_drc_zero','TOP_DRC_COUNT 0' in (ROOT/cdac/'artifacts/magic_full.log').read_text())
    bindings={
      'cdac':{'gds':cdac+'/artifacts/cdac_diff_routed.gds','gds_cell':'cdac_diff_routed','view':cdac+'/artifacts/cdac_diff_routed_flat_rc.spice','subckt':'cdac_diff_routed_flat_rc','view_kind':'analog_extracted_rc'},
      'sampling_switch':{'gds':switch+'/artifacts/dummy_layout_final/adc_tgate_layout.gds','gds_cell':'adc_tgate_layout','view':switch+'/artifacts/dummy_layout_final/adc_tgate_flat.rc.spice','subckt':'adc_tgate_flat','view_kind':'analog_extracted_rc'},
      'digital':{'gds':digital+'/artifacts/gds/sar_controller.gds','gds_cell':'sar_controller','view':digital+'/artifacts/spice/sar_controller.spice','subckt':'sar_controller','view_kind':'lvs_connectivity_only','gate_netlist':digital+'/artifacts/pnl/sar_controller.pnl.v','spef':digital+'/artifacts/spef/nom/sar_controller.nom.spef','sdf':digital+'/artifacts/sdf/nom_tt_025C_1v80/sar_controller__nom_tt_025C_1v80.sdf'}}
    for name,b in bindings.items():
        b['pins']=subckt(ROOT/b['view'],b['subckt']);b['counts']=rc_counts(ROOT/b['view'])
        for k in ('gds','view','gate_netlist','spef','sdf'):
            if k in b:b[k+'_sha256']=sha(ROOT/b[k])
        if b['view_kind']=='analog_extracted_rc':check(name+':positive_rc',b['counts']['positive_resistors']>0 and b['counts']['positive_capacitors']>0)
    expected=[f'{side}_{pin}' for side in ('P','N') for pin in ['TOP']+[f'B{i}' for i in range(11,-1,-1)]+['DUMMY','EDGE_BIAS']]
    check('cdac:pin_order',bindings['cdac']['pins']==expected)
    check('sampling_switch:directional_pin_order',bindings['sampling_switch']['pins']==['A','B','EN','ENB','VDD','VSS'])
    check('cdac:mim_count',bindings['cdac']['counts']['mim_devices']==8712)
    for rel in ['v2/config/spec.json',digital+'/results/physical_validation.json',switch+'/results/sampling_switch_release.json',cdac+'/qualification.json']:
        hashes[rel]=sha(ROOT/rel)
    missing=['frontend','comparator_and_preamp','reference_selection_and_distribution','nonoverlap_phase_and_clock_drive','core_interconnect_and_power_routing']
    audit={'status':'EXISTING_MACRO_EVIDENCE_AUDIT_PASS' if all(x['passed'] for x in checks) else 'EXISTING_MACRO_EVIDENCE_AUDIT_FAIL','checks':checks,'failed_checks':[x for x in checks if not x['passed']],'bindings':bindings,'source_sha256':hashes,'missing_physical_blocks':missing,'unretained_switch_intermediates':omitted_intermediates,'full_core_layout_complete':False,'top_level_parasitics_extracted':False,'digital_spice_warning':'This SPICE has no R/C and has abstract cell definitions. It is an LVS topology view; do not use it as complete transistor RC post-layout evidence.'}
    # Preserve the extracted element lines byte-for-byte; expose Magic's substrate node.
    raw=(ROOT/bindings['cdac']['view']).read_text()
    raw=raw.replace('.subckt cdac_diff_routed_flat_rc ','.subckt cdac_diff_routed_substrate_bound VSUBS ',1)
    raw=raw.replace('.ends cdac_diff_routed_flat_rc','.ends cdac_diff_routed_substrate_bound')
    adapted=HERE/'cdac_diff_routed_substrate_bound.spice'
    adapted.write_text(raw)
    check('cdac:substrate_adapter_preserves_elements',[x for x in spice_lines(adapted) if not x.lower().startswith(('.subckt','.ends'))]==[x for x in spice_lines(ROOT/bindings['cdac']['view']) if not x.lower().startswith(('.subckt','.ends'))])
    bindings['cdac']['bound_view']=adapted.relative_to(ROOT).as_posix()
    bindings['cdac']['bound_view_sha256']=sha(adapted)
    bindings['cdac']['bound_subckt']='cdac_diff_routed_substrate_bound'
    bindings['cdac']['bound_pins']=['VSUBS']+expected
    audit['status']='EXISTING_MACRO_EVIDENCE_AUDIT_PASS' if all(x['passed'] for x in checks) else 'EXISTING_MACRO_EVIDENCE_AUDIT_FAIL'
    (HERE/'macro_evidence_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    (HERE/'extracted_view_bindings.json').write_text(json.dumps({'scope':'PARTIAL_MACRO_BINDINGS_ONLY','bindings':bindings,'missing_required_views':missing,'full_core_extracted_view':None,'frozen_source_sha256':hashes},indent=2)+'\n')
    # Wrapper instantiates only two real extracted clamps and the real CDAC RC view.
    # The ports expose the missing reference selection network and clocks explicitly.
    ports=expected+['VCM_CLAMP','SAMPLE','SAMPLEB','VDD','VSS']
    def continuation(prefix,tokens,width=9):
        return '\n'.join((prefix if i==0 else '+')+' '+' '.join(tokens[i:i+width]) for i in range(0,len(tokens),width))
    wrapper=['* PARTIAL ELECTRICAL FIXTURE; NO TOP-LEVEL ROUTING PARASITICS; NOT FULL ADC', '* A is driven VCM; B is the held CDAC top. Never swap A/B.', '* Invoke from repository root. Both include paths name the frozen extracted views.']
    for key in ['cdac','sampling_switch']:wrapper.append('.include "'+bindings[key].get('bound_view',bindings[key]['view'])+'"')
    wrapper += [continuation('.subckt cdac_clamp_pex_partial',ports),continuation('XCDAC',['VSS']+expected+[bindings['cdac']['bound_subckt']]),'XCLAMP_P VCM_CLAMP P_TOP SAMPLE SAMPLEB VDD VSS adc_tgate_flat','XCLAMP_N VCM_CLAMP N_TOP SAMPLE SAMPLEB VDD VSS adc_tgate_flat','.ends cdac_clamp_pex_partial']
    (HERE/'cdac_clamp_pex_partial.spice').write_text('\n'.join(wrapper)+'\n')
    spec=read('v2/config/spec.json');q=spec['qualification'];rows=[]
    for gain in spec['gains']:
      for proc in q['process_corners']:
       for vdd in q['supply_voltages_v']:
        for temp in q['temperatures_c']:
         nominal=proc=='TT' and vdd==1.8 and temp==27
         rows.append({'id':f'G{gain}_{proc}_{vdd}V_{temp}C','gain':gain,'process':proc,'vdd_v':vdd,'temperature_c':temp,'status':'NOT_RUN','requirements':{'sndr_db_min':q['nominal_sndr_db'] if nominal else q['corner_sndr_db'],'core_power_w_max':q['nominal_core_power_w'] if nominal else q['corner_core_power_w'],'settling_error_lsb_max':q['settling_error_lsb'],'calibration_residual_lsb_max':q['nominal_calibration_residual_lsb'] if nominal else q['corner_calibration_residual_lsb'],'inl_abs_lsb_max':q['inl_abs_lsb'],'dnl_min_lsb_min':q['dnl_min_lsb'],'dnl_max_lsb_max':q['dnl_max_lsb'],'phase_margin_deg_min':q['phase_margin_deg'],'sample_rate_hz_min':spec['spec']['sample_rate_hz'],'fft_samples_min':spec['analysis']['fft_samples']}})
    (HERE/'postlayout_acceptance_matrix.json').write_text(json.dumps({'scope':'FULL_CORE_REQUIRED; NO SIMULATIONS EXECUTED BY THIS FILE','spec_sha256':sha(ROOT/'v2/config/spec.json'),'lsb_v':spec['spec']['full_scale_vpp']/2**spec['spec']['bits'],'system_mismatch_static_samples_min':q['mismatch_static_samples_min'],'rows':rows,'stimulus_contract':{'source_resistance_per_leg_ohm':q['source_resistance_per_leg_ohm'],'common_mode_offsets_v':q['common_mode_offsets_v'],'source_resistance_sensitivity_ohm':q['source_resistance_sensitivity_ohm'],'frontend_tones_hz':spec['analysis']['tone_targets_hz'],'adc_tone_hz':spec['analysis']['adc_tone_target_hz'],'calibration':'One frozen affine coefficient pair per gain at nominal; use independent holdout, do not refit each corner.','noise':'SNDR evidence must include a qualified time-varying device-noise method, not only noiseless transient FFT.','reference_mode':'UNFROZEN: tracking versus fixed must be selected or both qualified.'}},indent=2)+'\n')
    print(json.dumps({'status':audit['status'],'checks':len(checks),'failures':audit['failed_checks'],'matrix_rows':len(rows),'cdac_counts':bindings['cdac']['counts'],'digital_counts':bindings['digital']['counts']},indent=2))
    return 0 if all(x['passed'] for x in checks) else 1
if __name__=='__main__':raise SystemExit(main())
