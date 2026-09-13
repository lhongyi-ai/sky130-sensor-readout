#!/usr/bin/env python3
"""Noise, startup, and real PDK TG/CDAC-load experiments.

Independent block evidence only: not ADC conversion, SNDR, silicon, or PEX.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from run_frontend import HERE, header, run_deck, validate_log
from measurements import integrator, checked_data, interval_stats
from measurement_evidence import (require_nominal_or_fixed_calibration, snapshot_calibration,
                                  verify_manifest, write_manifest, write_analysis, sha256)

p=argparse.ArgumentParser()
p.add_argument("test",choices=["noise","startup","sampling","linearity","gain"])
p.add_argument("--gain",type=int,choices=[1,4,16],default=4)
p.add_argument("--corner",default="tt")
p.add_argument("--vdd",type=float,default=1.8)
p.add_argument("--temp",type=float,default=27)
p.add_argument("--ramp-us",type=float,default=1)
p.add_argument("--out",default="results/advanced")
p.add_argument("--analyze-only",action="store_true")
p.add_argument("--switchable",action="store_true")
p.add_argument("--isolation-r",type=float,default=150)
p.add_argument("--calibration-from",default=None)
p.add_argument("--core",default="frontend_pdk.spice")
p.add_argument("--acquisition-us",type=float,default=2.476847754,
               help="Conservative real-phase-generator acquisition window; older results retain their decks")
p.add_argument('--transient-method',choices=['trap','gear'],default='trap')
p.add_argument('--max-step-ns',type=float,default=5)
p.add_argument('--sampling-switch-file',default=None,help='optional frozen PDK sampling switch; ADC MIM bank remains unchanged')
p.add_argument('--sampling-switch-subckt',choices=['adc_tgate','adc_tgate_dual_lvt_dummy'],default='adc_tgate')
a=p.parse_args()
if a.test=='linearity' and not a.analyze_only:
    require_nominal_or_fixed_calibration(a.vdd, a.temp, a.calibration_from)
folder=HERE/a.out/f"{a.test}_{a.corner}_{a.vdd:g}_{a.temp:g}_g{a.gain}_r{a.ramp_us:g}{'_sw' if a.switchable else ''}{('_iso'+str(a.isolation_r)) if a.isolation_r!=150 else ''}"
folder.mkdir(parents=True,exist_ok=True)
config=folder/'experiment_config.json'
if a.analyze_only:
    verified_manifest=verify_manifest(folder)
    if not config.exists():
        raise ValueError('Legacy experiment lacks immutable settings; do not re-label it using current CLI defaults. Run a new experiment or a separately recorded legacy audit.')
    a=argparse.Namespace(**json.loads(config.read_text()))
    a.analyze_only=True
    if a.test=='linearity':
        require_nominal_or_fixed_calibration(a.vdd, a.temp, a.calibration_from)
    validate_log(folder/(a.test+'.log'))
    prior_summary=json.loads((folder/'summary.json').read_text())
else:
    if config.exists() or (folder/(a.test+'.spice')).exists():
        raise FileExistsError('Experiment already exists; choose a new output directory. Never overwrite old stimuli/ADC snapshots.')
    config.write_text(json.dumps(vars(a),indent=2)+'\n')
core=folder/"frontend_pdk_snapshot.spice"
if not a.analyze_only:
    if core.exists() and core.read_bytes() != (HERE/a.core).read_bytes():
        raise ValueError("Existing experiment belongs to a different circuit revision; choose a new --out")
    core.write_bytes((HERE/a.core).read_bytes())
else:
    if hashlib.sha256(core.read_bytes()).hexdigest()!=prior_summary['circuit_sha256']:
        raise ValueError('Frozen circuit snapshot changed since the recorded experiment')
g=a.gain
base=header(a.corner,a.vdd,a.temp,core)
if a.test in ['sampling','startup']:
    base+=f'.options method={a.transient_method} maxord=2\n'
common=f"""
RSP SP IP 350
RSN SN IN 350
XPGA IP IN OP ON VDD 0 VCM sky130_v2_pga RF=10000 RG={10000/g-350}
"""
if a.switchable:
    common=f"""
RSP SP IP 350
RSN SN IN 350
VSEL0 SEL0 0 {a.vdd if g==4 else 0}
VSEL1 SEL1 0 {a.vdd if g==16 else 0}
XPGA IP IN OP ON VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga
"""
control=".control\nset noaskquit\nset wr_singlescale\nset wr_vecnames\n"
result={"test":a.test,"gain":g,"corner":a.corner,"vdd_v":a.vdd,"temp_c":a.temp,
        "gain_implementation":"real transistor gain-select network, fixed select during this test" if a.switchable else "static resistor configuration",
        "circuit_source":a.core,
        "circuit_sha256":hashlib.sha256(core.read_bytes()).hexdigest(),
        "evidence_level":"SKY130 PDK transistor + passive, pre-layout block experiment"}
result['artifact_integrity_status']=(
    'VERIFIED_IMMUTABLE_MANIFEST' if a.analyze_only and verified_manifest else
    'UNVERIFIED_LEGACY_ARTIFACTS' if a.analyze_only else 'NEW_IMMUTABLE_MANIFEST')
result['analysis_code_sha256']=sha256(Path(__file__))
result['measurement_helpers_sha256']=sha256(HERE/'measurements.py')
if a.analyze_only:
    result['analysis_note']='Reanalysis only; original stimuli, raw results and summary remain unchanged.'
    if not verified_manifest:
        result['artifact_integrity_warning']='Legacy run has no immutable manifest; raw/configuration/deck integrity is not verified.'
if a.test=='gain':
    text=base+f'VIP SP 0 dc {a.vdd/2} ac 0.5\nVIN SN 0 dc {a.vdd/2} ac -0.5\n'+common+control+'''
op
wrdata op_nodes.dat all
ac dec 20 1 10meg
let od=v(op)-v(on)
let ore=real(od)
let oim=imag(od)
wrdata gain.dat ore oim
quit
.endc
.end
'''
    if not a.analyze_only:
        run_deck('gain',text,folder)
    ac=checked_data(folder/'gain.dat',stop=1e7)
    re=float(np.interp(1000,ac[:,0],ac[:,1]));im=float(np.interp(1000,ac[:,0],ac[:,2]))
    result.update({'gain_magnitude_at_1khz':float(np.hypot(re,im)),
                   'phase_deg_at_1khz':float(np.degrees(np.arctan2(im,re))),
                   'correct_closed_loop_polarity':re>0,
                   'caution':'DC operating point and small-signal closed-loop polarity/gain only, no finite-load, full-swing, settling or SNDR signoff.'})
elif a.test=="linearity":
    text=base+f"VIP SP 0 {a.vdd/2}\nBIN SN 0 v={a.vdd}-v(sp)\n"+common+"CLP OP 0 81.285p\nCLN ON 0 81.285p\n"+control+f"""
op
wrdata op_nodes.dat all
dc VIP {a.vdd/2-0.2/g} {a.vdd/2+0.2/g} {0.005/g}
let od=v(op)-v(on)
let id=v(sp)-v(sn)
let cm=(v(op)+v(on))/2
wrdata linearity.dat id od cm
quit
.endc
.end
"""
    if not a.analyze_only:
        run_deck("linearity",text,folder)
    tr=checked_data(folder/'linearity.dat')
    target=tr[:,1]*g
    if len(tr)!=81 or abs(target[0]+.4)>1e-6 or abs(target[-1]-.4)>1e-6:
        raise ValueError('Static test must cover all81 points over the complete defined range')
    anchors=np.array([np.argmin(abs(target-v)) for v in [-0.32,0,0.32]])
    if a.calibration_from:
        if not a.analyze_only:
            calibration_path,calibration_core=snapshot_calibration(HERE/a.calibration_from,folder)
        elif (folder/'calibration_source_summary.json').exists():
            calibration_path=folder/'calibration_source_summary.json'
            calibration_core=folder/'calibration_source_frontend.spice'
        elif verified_manifest:
            raise ValueError('Verified fixed-calibration experiment lacks its frozen calibration source')
        else:
            calibration_path=HERE/a.calibration_from
            calibration_core=calibration_path.parent/'frontend_pdk_snapshot.spice'
            result['legacy_calibration_warning']='Unverified legacy calibration source is read from its historical path.'
        calibration=json.loads(calibration_path.read_text())
        if calibration_core.read_bytes()!=core.read_bytes():
            raise ValueError("Calibration and test must use the identical frozen circuit revision")
        if calibration["gain"]!=g or calibration["corner"]!=a.corner or calibration["vdd_v"]!=1.8 or calibration["temp_c"]!=27:
            raise ValueError("Fixed calibration must come from samegain/samecorner at1.8V27C")
        if calibration['gain_implementation']!=result['gain_implementation']:
            raise ValueError('Calibration and test must instantiate the same static/switchable topology')
        fit=np.array(calibration["calibration_coefficients"])
        result['calibration_source_summary_sha256']=sha256(calibration_path)
        result['calibration_source_circuit_sha256']=sha256(calibration_core)
    else:
        fit=np.polyfit(tr[anchors,2],target[anchors],1)
    calibrated=tr[:,2]*fit[0]+fit[1]
    hold=np.ones(len(tr),dtype=bool)
    hold[anchors]=False
    residual=calibrated-target
    result.update({"calibration_points_output_equivalent_v":[-0.32,0,0.32],
        "calibration_source":a.calibration_from or "this nominal/static experiment",
        "calibration_coefficients":fit.tolist(),"max_holdout_error_lsb":float(np.max(abs(residual[hold]))/(0.8/4096)),
        "holdout_1LSB_gate":bool(np.max(abs(residual[hold]))<=0.8/4096),
        "fixed_calibration_4LSB_gate":bool(np.max(abs(residual[hold]))<=4*0.8/4096) if a.calibration_from else None,
        "max_output_cm_error_v":float(np.max(abs(tr[:,3]-a.vdd/2))),
        "caution":"Frontend DC transfer after three-point linear calibration; not ADC INL/DNL or noise-bearing conversion accuracy."})
elif a.test=="noise":
    devices={"xinp":"nfet","xinn":"nfet","xlp":"pfet","xln":"pfet","xop":"nfet","xon":"nfet","xip":"pfet","xin":"pfet","xtail":"nfet","xtcas":"nfet","xbn1":"nfet","xbn2":"nfet"}
    if "XINP2 " in core.read_text():
        devices.update({"xinp2":"nfet","xinp3":"nfet","xinn2":"nfet","xinn3":"nfet"})
    if "fdda_error_pair" in core.read_text():
        instances=range(1,7) if 'XP6 DP IP' in core.read_text() else range(1,4)
        devices={f"xerr{side}.x{pol}{j}":"nfet" for side in ["p","n"] for pol in ["p","n"] for j in instances}
        devices.update({"xlp":"pfet","xlp2":"pfet","xln":"pfet","xln2":"pfet","xop":"nfet","xon":"nfet"})
        if 'XLP3 ' in core.read_text():
            devices.update({'xlp3':'pfet','xln3':'pfet'})
    vectors=[f"onoise.m.xpga.xamp.{name}.msky130_fd_pr__{kind}_01v8" for name,kind in devices.items()]
    vector_text=" ".join(vectors+[v+".1overf" for v in vectors]+[v+".id" for v in vectors])
    text=base+f"VIP SP 0 dc {a.vdd/2} ac 1\nBIN SN 0 v={a.vdd}-v(sp)\n"+common+"""
XRIP OP NOP 0 frontend_r R=150
XRIN ON NON 0 frontend_r R=150
XCFP NOP 0 frontend_c4p
XCFN NON 0 frontend_c4p
CLP NOP 0 81.285p
CLN NON 0 81.285p
""".replace("R=150",f"R={a.isolation_r}")+control+"""
op
wrdata op_nodes.dat all
let pdc=-v(vdd)*i(vdd)
let pvcm=-v(vcm)*i(vcm)
wrdata power.dat pdc pvcm
noise v(nop,non) VIP dec 100 1 1g 1
setplot noise1
display
wrdata noise.dat onoise_spectrum inoise_spectrum
quit
.endc
.end
"""
    if not a.analyze_only:
        text=text.replace("wrdata noise.dat onoise_spectrum inoise_spectrum", "wrdata noise.dat onoise_spectrum inoise_spectrum\nwrdata contributors.dat "+vector_text)
        if 'fdda_error_pair' in core.read_text():
            op_devices={'input':'xerrp.xp1','tail':'xerrp.xt','output':'xop',
                        'cm_tail':'xcmt','bias':'xbn1'}
            if 'XT0 TS BN VSS VSS' in core.read_text():
                op_devices['tail']='xerrp.xt0'
                result['tail_operating_point_scope']='XT0 is one current-setting device of a parallel/cascoded tail; its id is not the total tail current.'
            op_vectors=[f'@m.xpga.xamp.{dev}.msky130_fd_pr__nfet_01v8[{field}]'
                        for dev in op_devices.values() for field in ['id','gm','gds','vds','vdsat']]
            text=text.replace('wrdata power.dat pdc pvcm','wrdata power.dat pdc pvcm\nwrdata device_op.dat '+' '.join(op_vectors))
        run_deck("noise",text,folder)
    n=checked_data(folder/'noise.dat',stop=1e9)
    if (folder/"power.dat").exists():
        power=np.loadtxt(folder/"power.dat",skiprows=1,ndmin=2)
        result["dc_power_w"]=float(power[0,1])
        result['dc_power_basis']='VDD rail only; external common-mode port reported separately when available'
        if power.shape[1]>2:
            result['common_mode_port_dc_power_w']=float(power[0,2])
            result['total_vdd_and_common_mode_dc_power_w']=float(power[0,1]+power[0,2])
    integrator=np.trapezoid if hasattr(np,"trapezoid") else np.trapz
    for end in [5000,50000,1e9]:
        mean_psd,_=interval_stats(n[:,0],n[:,1]**2,1,end)
        result[f"output_noise_1_to_{end:g}Hz_rms_v"]=float(np.sqrt(mean_psd*(end-1)))
    result["noise_at_1khz_v_per_rtHz"]=float(np.interp(1000,n[:,0],n[:,1]))
    result["isolation_r_ohm_per_side"]=a.isolation_r
    result["caution"]=f"Continuous-time noise after{a.isolation_r:g}ohm/4pF isolation, static81.285pF/side load. NOT sampled/aliased system noise or SNDR. Consult retained deck for older revisions."
    if (folder/"contributors.dat").exists():
        parts=np.loadtxt(folder/"contributors.dat",skiprows=1)
        contributors=[]
        for j,name in enumerate(devices):
            row={"device":name}
            for end in [5000,1e9]:
                for label,off in [("total",0),("flicker",len(devices)),("channel",2*len(devices))]:
                    mean_psd,_=interval_stats(parts[:,0],parts[:,1+j+off]**2,1,end)
                    row[f"{label}_1_to_{end:g}Hz_rms_v"]=float(np.sqrt(mean_psd*(end-1)))
            contributors.append(row)
        result["selected_mos_noise_contributors"]=sorted(contributors,key=lambda r:r["total_1_to_1e+09Hz_rms_v"],reverse=True)
elif a.test=="startup":
    ramp=a.ramp_us*1e-6
    stop=max(100e-6,3*ramp)
    base=base.replace(f"VDD VDD 0 {a.vdd}",f"VDD VDD 0 PWL(0 0 {ramp} {a.vdd} {stop} {a.vdd})")
    base=base.replace(f"VCM VCM 0 {a.vdd/2}","BVCM VCM 0 v=v(vdd)/2")
    text=base+"BIP SP 0 v=v(vdd)/2\nBIN SN 0 v=v(vdd)/2\n"+common+"CLP OP 0 81.285p\nCLN ON 0 81.285p\n"+control+f"""
tran 20n {stop} uic
let cm=(v(op)+v(on))/2
wrdata startup.dat v(vdd) cm v(xpga.xamp.bn) v(xpga.xamp.bp) v(xpga.xamp.start) i(vdd)
quit
.endc
.end
"""
    if not a.analyze_only:
        run_deck("startup",text,folder)
    tr=checked_data(folder/'startup.dat',stop=stop)
    result.update({"ramp_s":ramp,"final_output_cm_v":float(tr[-1,2]),
        "final_bn_v":float(tr[-1,3]),"final_bp_v":float(tr[-1,4]),
        "final_startup_gate_v":float(tr[-1,5]),"final_supply_current_a":float(-tr[-1,6]),
        "startup_gate_shutoff_below_0p2V":bool(tr[-1,5]<0.2),
        "final_cm_within_50mV":bool(abs(tr[-1,2]-a.vdd/2)<0.05),
        "caution":"UIC supply-ramp test; not comprehensive startup/temperature proof."})
else:
    adc=folder/"adc_blocks_snapshot.spice"
    if not a.analyze_only:
        adc.write_bytes((HERE.parent/"adc/adc_blocks.spice").read_bytes())
    elif hashlib.sha256(adc.read_bytes()).hexdigest()!=prior_summary['adc_sampler_source_sha256']:
        raise ValueError('Frozen ADC sampler snapshot changed since the recorded experiment')
    extra_include=''
    extra_switch=getattr(a,'sampling_switch_file',None)
    if extra_switch:
        extra_snapshot=folder/'sampling_switch_snapshot.spice'
        if not a.analyze_only:
            extra_snapshot.write_bytes((HERE/extra_switch).read_bytes())
        elif hashlib.sha256(extra_snapshot.read_bytes()).hexdigest()!=prior_summary['extra_sampling_switch_sha256']:
            raise ValueError('Frozen alternate switch changed since the recorded experiment')
        extra_include=f'.include {extra_snapshot}\n'
        result['extra_sampling_switch_sha256']=hashlib.sha256(extra_snapshot.read_bytes()).hexdigest()
    elif getattr(a,'sampling_switch_subckt','adc_tgate')!='adc_tgate':
        raise ValueError('Alternate sampling switch requires an explicit source snapshot')
    text=base+f".include {adc}\n"+f"""
VIP SP 0 PULSE({a.vdd/2-0.18/g} {a.vdd/2+0.18/g} 10u 10n 10n 10u 20u)
VIN SN 0 PULSE({a.vdd/2+0.18/g} {a.vdd/2-0.18/g} 10u 10n 10n 10u 20u)
"""+common+f"""
VACQ ACQ 0 PULSE(0 {a.vdd} 10u 1n 1n {a.acquisition_us}u 10u)
VACQB ACQB 0 PULSE({a.vdd} 0 10u 1n 1n {a.acquisition_us}u 10u)
VRST RST 0 PULSE(0 {a.vdd} 8u 1n 1n 1u 10u)
VRSTB RSTB 0 PULSE({a.vdd} 0 8u 1n 1n 1u 10u)
XRIP OP FILTP 0 frontend_r R=150
XRIN ON FILTN 0 frontend_r R=150
XCFP FILTP 0 frontend_c4p
XCFN FILTN 0 frontend_c4p
XTGP FILTP HP ACQ ACQB VDD 0 adc_tgate
XTGN FILTN HN ACQ ACQB VDD 0 adc_tgate
XCP HP VCM adc_mim_bank COUNT=4096
XCN HN VCM adc_mim_bank COUNT=4096
XRSTP VCM HP RST RSTB VDD 0 adc_tgate
XRSTN VCM HN RST RSTB VDD 0 adc_tgate
* Explicit testbench leakage only, avoids mathematically floating held nodes.
RLEAKP HP VCM 1g
RLEAKN HN VCM 1g
"""+control+"""
tran {a.max_step_ns}n 40u 0 {a.max_step_ns}n
let od=v(op)-v(on)
let hd=v(hp)-v(hn)
let cm=(v(op)+v(on))/2
wrdata sampling.dat od hd cm v(acq) v(sp) v(sn) i(vdd) i(vcm)
quit
.endc
.end
""".replace('{a.max_step_ns}',str(a.max_step_ns))
    if extra_include:
        text=text.replace(f'.include {adc}\n',f'.include {adc}\n'+extra_include)
        text=text.replace('VDD 0 adc_tgate\n',f'VDD 0 {a.sampling_switch_subckt}\n')
    result['sampling_switch_subcircuit']=getattr(a,'sampling_switch_subckt','adc_tgate')
    if not a.analyze_only:
        run_deck("sampling",text.replace("R=150",f"R={a.isolation_r}"),folder)
    tr=checked_data(folder/'sampling.dat',stop=40e-6)
    samples=[]
    for end in [(start+a.acquisition_us)*1e-6-10e-9 for start in [10,20,30]]:
        # Endpoint reference is same cycle's settled amplifier output, not ideal gain.
        ref,ripple=interval_stats(tr[:,0],tr[:,1],end+3e-6,end+4e-6)
        reference_stable=ripple<=0.8/4096/40
        held=float(np.interp(end,tr[:,0],tr[:,2]))
        err=float(held-ref)
        after=float(np.interp(end+30e-9,tr[:,0],tr[:,2]))
        hold_error=after-float(ref)
        samples.append({"time_s":end,"sampled_diff_v":float(held),"settled_pga_diff_v":float(ref),
                        "dynamic_error_v":err,"within_0p25LSB":bool(reference_stable and abs(err)<=0.8/4096/4),
                        "reference_peak_to_peak_v":ripple,"reference_stable_within_0p025LSB":bool(reference_stable),
                        "after_switch_opens_time_s":end+30e-9,
                        "held_after_switch_opens_v":after,"post_aperture_error_v":hold_error,
                        "post_aperture_within_0p25LSB":bool(reference_stable and abs(hold_error)<=0.8/4096/4)})
    result.update({"samples":samples,"all_dynamic_samples_pass":all(x["within_0p25LSB"] for x in samples),
        "all_post_aperture_samples_pass":all(x["post_aperture_within_0p25LSB"] for x in samples),
        "load_pf_per_side":81.28512,"source_r_ohm_per_side":350,"isolation_r_ohm_per_side":a.isolation_r,
        "reservoir_cap_nominal_pf_per_side":4,
        "acquisition_window_s":a.acquisition_us*1e-6,
        "transient_method":a.transient_method,"max_step_s":a.max_step_ns*1e-9,
        "adc_sampler_source_sha256":hashlib.sha256(adc.read_bytes()).hexdigest(),
        "max_common_mode_error_v":float(np.max(abs(tr[:,3]-a.vdd/2))),
        "common_mode_within_50mV":bool(np.max(abs(tr[:,3]-a.vdd/2))<=0.05),
        "mean_frontend_power_w":float(-a.vdd*integrator(tr[:,7],tr[:,0])/(tr[-1,0]-tr[0,0])) if tr.shape[1]>7 else None,
        "power_basis":"VDD rail only; VCM delivered/absorbed power reported separately when saved",
        "mean_common_mode_port_power_w":float(-a.vdd/2*integrator(tr[:,8],tr[:,0])/(tr[-1,0]-tr[0,0])) if tr.shape[1]>8 else None,
        "sampling_measurement_scope":"Three acquisition-end and immediate post-aperture points only; no full conversion-hold qualification.",
        "full_conversion_hold_qualified":False,
        "required_conversion_hold_s":7.5e-6,
        "testbench_hold_before_reset_s":(8-a.acquisition_us)*1e-6-2e-9,
        "alternate_switch_replaced_instances":["XTGP","XTGN","XRSTP","XRSTN"] if extra_include else [],
        "switch_connection_note":"A is FILTP/FILTN for sampling or VCM for reset; B is held HP/HN in both groups. Alternate switch replaces both sampling and reset groups.",
        "caution":"Real PDK TG and MIM bank with ideal complementary clocks/testbench CM reset. Only acquisition/aperture-local checks; reset shortens hold below 7.5 us. NOT full SAR bit switching/comparator kickback, clock-driver power, sampled noise or system SNDR."})
if a.analyze_only:
    analysis_path=write_analysis(folder,result)
    print(json.dumps({'analysis_report':str(analysis_path),'original_summary_unchanged':True}))
else:
    (folder/"summary.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    write_manifest(folder,required=['experiment_config.json','frontend_pdk_snapshot.spice',
                                   a.test+'.spice',a.test+'.log',a.test+'.dat','summary.json'],
                   producer_paths=[Path(__file__),HERE/'measurements.py',HERE/'measurement_evidence.py',HERE/'run_frontend.py'])
print(json.dumps(result,indent=2))
