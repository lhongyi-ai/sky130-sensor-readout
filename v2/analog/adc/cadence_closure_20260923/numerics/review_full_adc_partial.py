#!/usr/bin/env python3
"""Review retained partial full-ADC traces; does not qualify simulation accuracy."""
from pathlib import Path
import argparse
import json
import numpy as np
from psf_stream import Trace
from audit_saved_comparator import sha

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / "runs/task_20260924T022747927763Z/design"
P = "p2_ams_reset1."


def review(run,output):
    path = run / "amsdControl.raw/adc_closure_tran.tran.tran"
    trace = Trace(path)
    rows = list(trace.rows())
    names = trace.names
    t = np.array([r["time"] for r in rows])
    a = {n: np.array([r[n] for r in rows]) for n in names}
    del rows
    short = {n.removeprefix(P): n for n in names}
    def values(at):
        return {k: float(np.interp(at, t, a[v])) for k, v in short.items()}
    windows = []
    for label, lo, hi, warning in [("frame1_sample_start", 4.0624e-6, 4.10e-6, 4.0632e-6), ("frame2_sample_start", 14.0624e-6, 14.10e-6, 14.0751e-6)]:
        ix = (t >= lo) & (t <= hi)
        channels = ["sample_cmd_e", "conv_e", "acq_e", "top_e", "topb_e", "inp", "inn", "rp", "rn", "vcm", "adc.XADC_BP2", "adc.XADC_TP", "adc.XADC_TN"]
        range_data = {k: {"min_V": float(a[short[k]][ix].min()), "max_V": float(a[short[k]][ix].max())} for k in channels}
        crossings = {}
        for k in ["sample_cmd_e", "conv_e", "acq_e", "top_e", "topb_e"]:
            y = a[short[k]]
            for direction in ["rising", "falling"]:
                condition = (y[:-1] < .9) & (y[1:] >= .9) if direction == "rising" else (y[:-1] > .9) & (y[1:] <= .9)
                j = np.flatnonzero(condition & (t[:-1] >= lo) & (t[1:] <= hi))
                crossings[k+"_"+direction] = (t[j] + (.9-y[j])/(y[j+1]-y[j])*(t[j+1]-t[j])).tolist()
        near = values(warning)
        windows.append({"name": label, "window_s": [lo,hi], "logged_warning_time_s": warning, "warning_time_precision_note": "Logger rounds event time; interpolated snapshot is contextual, not the exact internal failing step.", "values_near_logged_time_V": {k: near[k] for k in channels}, "ranges_V": range_data, "half_supply_crossings": crossings, "minimum_saved_dt_s": float(np.diff(t[ix]).min()), "points": int(ix.sum())})
    endpoints=[]
    for frame, at in [(1,6.5615e-6),(2,16.5615e-6)]:
        v=values(at);errors={}
        for side,inp in [("P","inp"),("N","inn")]:
            for bit in range(12):errors[f"B{side}{bit}"]=v[f"adc.XADC_B{side}{bit}"]-v[inp]
        endpoints.append({"frame":frame,"time_s":at,"all_24_bottom_plate_tracking_errors_V":errors,"max_abs_V":max(map(abs,errors.values())),"scope":"Tracking before release, not charge injection or final sampling-error acceptance."})
    # The known external 1-ohm branches permit reference-current reconstruction.
    # Main supply, VCM, and ideal digital-driver power are NOT recoverable here.
    rp_s=a[P+"rp_source"];rn_s=a[P+"rn_source"]
    ip=(rp_s-a[P+"rp"])/1.0;inn=(rn_s-a[P+"rn"])/1.0
    power=rp_s*ip+rn_s*inn
    lo,hi=4.0625e-6,14.0625e-6
    grid=np.r_[lo,t[(t>lo)&(t<hi)],hi]
    p=np.interp(grid,t,power)
    source_energy=float(np.trapezoid(p,grid))
    resistor_loss=float(np.trapezoid(np.interp(grid,t,ip*ip+inn*inn),grid))
    cap_delta=sum(.5*10e-9*(float(np.interp(hi,t,a[P+k]))**2-float(np.interp(lo,t,a[P+k]))**2) for k in ["rp","rn"])
    references={"formula":"I_RP=(RP_source-RP)/1ohm, I_RN=(RN_source-RN)/1ohm; P_sources=RP_source*I_RP+RN_source*I_RN, signed external ideal-source delivered power.","first_frame_window_s":[lo,hi],"first_frame_source_energy_J":source_energy,"first_frame_source_average_W":source_energy/(hi-lo),"first_frame_external_1ohm_loss_J":resistor_loss,"first_frame_external_10nF_storage_change_J":cap_delta,"first_frame_reconstructed_reference_pin_energy_J":source_energy-resistor_loss-cap_delta,"reconstruction_limit":"Energy balance diagnostic only; trapezoidal accepted-time reconstruction, no saved native terminal currents or strict-pair accuracy yet. Source energy alone is NOT chip pin energy.","whole_trace_peak_abs_RP_source_current_A":float(np.max(abs(ip))),"whole_trace_peak_abs_RN_source_current_A":float(np.max(abs(inn))),"not_total_chip_power":True,"not_chip_power_pass":True,"missing":["native ADC RP/RN terminal currents for direct boundary validation","VDD source current","VCM source current","realized SAR RTL/control power","supply draw of ideal trial/sample/eval/reset voltage drivers"],"external_fixture":"1ohm reference source resistance and10nF external decoupling each. Source energy includes external resistor loss and external capacitor endpoint storage change."}
    existing=json.loads((run.parent/"review.json").read_text()) if (run.parent/"review.json").exists() else {}
    result={"status":"FULL_ADC_WAVEFORM_DIAGNOSIS_NOT_NUMERICALLY_QUALIFIED","integration_functional_pass":existing.get("functional_pass"),"raw_sha256":sha(path),"saved_interval_s":[float(t[0]),float(t[-1])],"points":len(t),"voltage_trace_count":len(names),"current_trace_count":0,"warnings":windows,"tracking_endpoints":endpoints,"reference_source_supply_diagnostic":references,"missing_waveform_nodes_for_mechanism":["phases.XPHASE_XBCONV_B (first PFET local gate)","adc.XADC_XP2_ACQB (second PFET local gate)","both flagged primitive :int_b/:dbnode/:sbnode voltages"],"notes":["No strict full-ADC waveform is analyzed here, so transient extrema are circuit behavior, not estimates of numerical error.","Two printed LTE warnings and matching output codes cannot qualify numerical accuracy or linearity.","Prior timeout evidence remains failed/incomplete; a subsequent complete run does not overwrite it.","Both flagged outer bulk terminals are already tied to VDD; internal int_b does not imply a missing schematic bulk connection."]}
    output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"points":len(t),"end_s":float(t[-1]),"tracking_endpoints_max_V":[e["max_abs_V"] for e in endpoints],"reference_source_supply_diagnostic":references},indent=2))


if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("run",type=Path,nargs="?",default=RUN);p.add_argument("output",type=Path,nargs="?",default=HERE/"full_adc_partial_review.json");args=p.parse_args()
    review(args.run,args.output)
