#!/usr/bin/env python3
"""Prepare only: real full ADC + RTL, a 4.1us local-grid diagnostic, never ADC PASS."""
import difflib, hashlib, importlib.util, json, re, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parent
ROOT = INTEGRATION.parents[4]
ADC = ROOT / 'v2/physical/cdac_repair_20260923/adc_native_mapping_1'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def dump(path, value): path.write_text(json.dumps(value, indent=2) + '\n')

def main():
    if any((HERE/x).exists() for x in ['baseline', 'strict', 'preparation_audit.json']):
        raise SystemExit('Refusing to replace a prepared or executed attempt')
    sources = {}
    # Integer femtoseconds avoid accumulated binary-float rounding in the schedule.
    points_fs = list(range(4063150000, 4063350000 + 1, 100))
    assert len(points_fs) == 2001 and all(b-a == 100 for a,b in zip(points_fs, points_fs[1:]))
    strobe = 'strobeoutput=all strobetimes=[' + ' '.join(str(t)+'f' for t in points_fs) + ']'
    contract = {'status':'PREPARED_NOT_RUN', 'scope':'SHORT_FIRST_PHASE_DIAGNOSTIC_ONLY',
        'stop_s':4.1e-6, 'forced_times_fs':points_fs, 'count':len(points_fs),
        'interval_fs':[points_fs[0],points_fs[-1]], 'step_fs':100,
        'all_accepted_points_required':True, 'original_two_frame_gate_V':.05*.8/4096,
        'original_two_frame_gate_status':'FAIL_RETAINED_NOT_REEVALUATED_BY_THIS_PROBE',
        'expected_completed_frames':0, 'expected_completed_decisions':0,
        'complete_ADC_qualified':False, 'long_campaign_allowed':False,
        'required_tool_version':'21.1.0.132.isr1',
        'window_selection':{'source_run':'task_20260924T053814697817Z',
          'raw_sha256':'3ef33020b514827023eefd71ab332b2016b4f3079a46056301de11b8e7c42946',
          'external_VDS_zero_interpolated_s':4.063200632662e-6,
          'CONV_halfrail_fall_s':4.063269705024839e-6,
          'CONV_halfrail_actual_bracket_s':[4.063269682762545e-6,4.063271095521810e-6],
          'reason':'Covers the observed VDS zero/internal-body LTE event and subsequent actual CONV halfrail crossing; selected before new runs.'}}
    dump(HERE/'forced_time_contract.json',contract)
    helper = ROOT/'v2/analog/noise_controls_20260923/doc_cache/tran_help.txt'
    assert sha(helper)=='9d5752608d6d259855ff3a613b9b36133634da81e03fb18fc30e9b467d5dc145'
    sources[str(helper.relative_to(ROOT))]=sha(helper)
    auditor = ROOT/'v2/analog/frontend/cadence_20260923/audit_native_netlist.py'
    spec=importlib.util.spec_from_file_location('native_auditor',auditor)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    native={}
    for label,objects,netlist,count in [
        ('ADC','reset1/objects.json','private_runtime/si_reset1_001/netlist',693),
        ('phase','phase_school_r1_objects.json','private_runtime/si_phase_001/netlist',48)]:
        obj=ADC/objects; net=ADC/netlist
        report=mod.audit(json.loads(obj.read_text()),net.read_text())
        assert report['status']=='NATIVE_NETLIST_AUDIT_PASS' and report['actual_count']==count,report
        native[label]={'count':count,'netlist_sha256':sha(net),'objects_sha256':sha(obj), 'fresh_audit':report}
    for profile in ['baseline','strict']:
        frozen=INTEGRATION/f'reset1_2frames_{profile}_v4'
        old=json.loads((frozen/'manifest.json').read_text())
        for name,digest in old['generated_file_hashes'].items():
            assert sha(frozen/name)==digest,('Frozen source changed',name)
        for label in ['ADC','phase']:
            assert old['native_body_hashes'][label]==native[label]['netlist_sha256']
        out=HERE/profile;out.mkdir();(out/'audits').mkdir()
        copied=['sar_controller.v','p1_interfaces.vams','p2_ams_reset1.vams','p2_sequence.sv','profile.vh','reset1_native_bound.scs']
        for name in copied: shutil.copyfile(frozen/name,out/name)
        assert sha(out/'sar_controller.v')=='5e65a4cff94ae8507d5830cd7c0c669be50ea6e1730b8d20b0893afc39e4dadf'
        for p in (frozen/'audits').iterdir():shutil.copyfile(p,out/'audits'/p.name)
        text=(frozen/'amsdControl.scs').read_text()
        needle='adc_closure_tran tran stop=40u'
        assert text.count(needle)==1
        new=text.replace(needle,'adc_closure_tran tran stop=4.1u')
        extra='save p2_ams_reset1.phases.XPHASE_XBCONV_B\nsave p2_ams_reset1.phases.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8:int_b sigtype=node\n'
        new=new.replace('adc_closure_tran tran ',extra+'adc_closure_tran tran ')
        new=re.sub(r'^(adc_closure_tran tran .*?)$',lambda m:m[1]+' '+strobe,new,flags=re.M)
        assert new.count('strobeoutput=all')==1 and 'strobeonly' not in new and 'relref=sigglobal' in new
        (out/'amsdControl.scs').write_text(new)
        shutil.copyfile(HERE/'run_template.sh',out/'run.sh')
        shutil.copyfile(HERE/'forced_time_contract.json',out/'forced_time_contract.json')
        dump(out/'audits'/'fresh_native_audit.json',native)
        (out/'audits'/'changes_vs_frozen_v4.diff').write_text(''.join(difflib.unified_diff(text.splitlines(True),new.splitlines(True),fromfile=frozen.name+'/amsdControl.scs',tofile=profile+'/amsdControl.scs')))
        manifest={**old,'status':'PREPARED_SHORT_DIAGNOSTIC_NOT_SIMULATED','frames':0,
          'frozen_sequence_requested_frames':2,'expected_completed_decisions':0,
          'expected_additional_aborted_frame':0,'accuracy_profile':profile,
          'source_frozen_directory':frozen.name,'source_frozen_manifest_sha256':sha(frozen/'manifest.json'),
          'intended_stop_s':4.1e-6,'only_changes_to_simulation_input':['stop 40us to 4.1us','add explicit common forced points and strobeoutput=all','add verified CONV local-gate and primitive int_b voltage saves'],
          'forced_contract_sha256':sha(HERE/'forced_time_contract.json'),
          'complete_ADC_qualified':False,'long_campaign_allowed':False,
          'scope':'No complete conversion. Do not call the full-ADC analyzer and do not interpret an exit0 as qualification.'}
        manifest['generated_file_hashes']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
        dump(out/'manifest.json',manifest)
        (out/'SHA256SUMS').write_text(''.join(digest+'  '+name+'\n' for name,digest in manifest['generated_file_hashes'].items())+sha(out/'manifest.json')+'  manifest.json\n')
        sources[str(frozen.relative_to(ROOT))+'/manifest.json']=sha(frozen/'manifest.json')
    a=(HERE/'baseline/amsdControl.scs').read_text()
    b=(HERE/'strict/amsdControl.scs').read_text()
    assert a.replace('reltol=1e-5 vabstol=1e-8 iabstol=1e-13','reltol=1e-6 vabstol=1e-9 iabstol=1e-14').replace('maxstep=2n','maxstep=1n')==b
    for name in copied:assert sha(HERE/'baseline'/name)==sha(HERE/'strict'/name)
    dump(HERE/'preparation_audit.json',{'status':'LOCAL_PREPARATION_AUDIT_PASS_NOT_CADENCE_EXECUTED',
        'fresh_native_count':{'ADC':693,'phase':48},'native_auditor_sha256':sha(auditor),
        'frozen_source_integrity':True,'same_physical_circuit_RTL_stimuli':True,
        'pair_differences_only_requested_accuracy':True,'identical_common_point_count':len(points_fs),
        'all_accepted_output_requested':True,'actual_strobe_acceptance':'MUST_VERIFY_SCHOOL_RAW',
        'actual_tolerances':'MUST_VERIFY_SCHOOL_RAW','sources':sources,
        'prepared_manifests_sha256':{p:sha(HERE/p/'manifest.json') for p in ['baseline','strict']},
        'prepare_script_sha256':sha(Path(__file__)),'complete_ADC_qualified':False,'long_campaign_allowed':False})
    print('LOCAL_PREPARATION_AUDIT_PASS; NO SIMULATION; NO ADC QUALIFICATION')

if __name__=='__main__':main()
