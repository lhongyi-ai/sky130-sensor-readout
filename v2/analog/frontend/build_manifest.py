#!/usr/bin/env python3
"""Evidence manifest for frontend prototypes; never implies chip completion."""
import hashlib
import json
from pathlib import Path
from run_frontend import validate_log

HERE=Path(__file__).resolve().parent
results=HERE/"results"
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

summaries=[]
for path in sorted(results.rglob("summary.json")):
    data=json.loads(path.read_text())
    item={"path":str(path.relative_to(HERE)),"summary":data,
          "summary_sha256":digest(path)}
    cal=data.get('calibration_source','') if isinstance(data,dict) else ''
    if isinstance(cal,str) and cal.startswith('results/'):
        reference=(HERE/cal).parent/'frontend_pdk_snapshot.spice'
        tested=path.parent/'frontend_pdk_snapshot.spice'
        if reference.exists() and tested.exists():
            item['calibration_circuit_revision_matches']=digest(reference)==digest(tested)
            if digest(reference)!=digest(tested):
                item['evidence_validity']='INVALID_CROSS_REVISION_CALIBRATION'
    summaries.append(item)

sources={str(p.relative_to(HERE)):digest(p) for p in sorted(HERE.iterdir()) if p.suffix in [".py",".spice",".md"]}
snapshots={str(p.relative_to(HERE)):digest(p) for p in sorted(results.rglob("*snapshot.spice"))}
datahash={str(p.relative_to(HERE)):digest(p) for p in sorted(results.rglob("*.dat"))}
logs=[]
for path in sorted(results.rglob("*.log")):
    text=path.read_text(errors="replace")
    try:
        validate_log(path)
        clean=True
    except RuntimeError:
        clean=False
    logs.append({"path":str(path.relative_to(HERE)),"sha256":digest(path),
                 "ngspice_done_marker":"ngspice-47 done" in text,"clean_completion":clean,
                 "contains_error":"Error:" in text})
report={
 "status":"PROTOTYPE_WITH_PASSES_AND_OPEN_FAILURES_NOT_FINAL_CHIP",
 "qualified_system":False,"cadence_used":False,"full_layout_drc_lvs_pex":False,
 "primary_circuit":"frontend_fdda.spice",
 "legacy_resistor_input_circuit":"frontend_pdk.spice",
 "frozen_candidate_sha256":"c231e378a499ddee7b950dcdc40714fa16a21b81b29de6fb8798ead36bc125e6",
 "frozen_candidate_suite":"results/frozen_fdda10",
 "primary_circuit_internal_ideal_resistors_capacitors_current_sources":[],
 "measurement_ideal_elements":["external stimulus/clock/reference voltages","static81.285pF load in AC/noise stress test","1Gohm hold-node testbench leakage"],
 "gain_interfaces":{"static":"sky130_v2_pga/sky130_v2_sample_driver","real_switches":"sky130_v2_switchable_pga","dynamic_gain_transition_qualified":False},
 "pvt_coverage":"Legacy gm3x_rz:135/135 cases run; original64pass, audited63pass72fail. FrozenFDDA10 onlyboundedTT VT/gain tests; neither is systemPVTsignoff.",
 "monte_carlo_200_samples_completed":False,
 "open_failures":["gm3x_rz fixed nominal calibration drifts77.6/92.7LSB at twoTT VT extremes","gm3x_rz auditedsampledload135matrix only63pass","FDDA10 nominalDC heldout1.359LSB exceeds1LSB","FDDA common-mode coupling/stability notclosed","full samplednoise/SNDR and physicalsignoff absent"],
 "historical_measurement_audit":"results/legacy_measurement_audit.json",
 "tool_environment":{"ngspice":"47","pdk":"sky130A combined continuous models","lib_path":"/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice","image":"hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7"},
 "source_sha256":sources,"snapshot_sha256":snapshots,"raw_data_sha256":datahash,
 "logs":logs,"experiments":summaries,
 "interpretation":"Read experiment-specific geometry snapshots. Synthetic/PDK block evidence is not full system, layout or silicon."
}
(results/"frontend_manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(f"Manifest: {len(summaries)} experiment summaries, {len(logs)} simulator logs, {len(snapshots)} snapshots; system qualified=False")
