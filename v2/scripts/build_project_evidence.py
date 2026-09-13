#!/usr/bin/env python3
"""Index evidence with its actual scope; never synthesize whole-chip PASS.

This is an audit/index, not a simulator. It records missing/stale evidence and
links frozen run reports. A successful index build does not qualify a circuit.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
EVIDENCE = [
    ("model_and_code","results/validation.json","Software/model/RTL tests only"),
    ("device_environment","environment/results/device_qualification.json","PDK single devices, 45 PVT and local mismatch controls"),
    ("mim_multiplier","environment/results/cap_multiplier_qualification.json","Unit-capacitor local mismatch scaling, not chip yield"),
    ("primitive_physical","environment/results/physical_qualification.json","MIM/NMOS tiny layouts; capacitive PEX"),
    ("digital_macro","physical/digital/results/physical_validation.json","Digital macro only: routed DRC/LVS/RC/STA"),
    ("digital_interface","physical/digital/results/interface_validation.json","Digital comparator-input loading/timing contract"),
    ("sampling_switch","physical/adc_switch/results/switch_validation.json","Check report model/run: old failures remain evidence"),
    ("sampling_switch_release","physical/adc_switch/results/sampling_switch_release.json","Final standalone four-MOS sampling-switch release: 45 PVT, bounded source/common-mode/input grid, schematic and extracted-RC only; not a full ADC"),
    ("sampling_dummy_schematic","physical/adc_switch/results/dummy_w4w8_full.json","Four-device switch standalone schematic grid only"),
    ("sampling_dummy_rc","physical/adc_switch/results/dummy_w4w8_rc_full.json","Four-device switch standalone RC grid only"),
    ("sampling_fullscale_boundaries","physical/adc_switch/results/dummy_fullscale_boundaries.json","216 opposite-full-scale boundary view cases at four selected PVT points, not full 45-PVT coverage"),
    ("adc_index","analog/adc/summary.json","Historical ADC block index with explicit open qualification items; new live-RTL runs have separate entries"),
    ("phase_generator","integration/results/phase_qualification.json","45 deterministic standalone schematic phase PVT points"),
    ("cdac_mismatch","analog/adc/results/cdac_mismatch_summary.json","200 capacitor-array-only PDK samples; computed ideal charge transfer"),
    ("comparator_initial_mismatch","analog/adc/results/comparator_mismatch_summary.json","Initial comparator-only screen; wider refinements are separate"),
    ("comparator_fixed_vt","analog/adc/results/comparator_calibration_vt_summary.json","200 bare retained-comparator instances with fixed nominal offset at four V/T extremes; excludes new preamp, floating CDAC, and full-chain calibration"),
    ("adc_preamp","analog/adc/results/preamp_summary.json","Continuous preamp characterization, not sampled ADC noise"),
    ("original_frontend_matrix","analog/frontend/results/gm3x_rz_matrix/summary.json","135 front-end sampling subset, includes real failures"),
    ("frontend_measurement_audit","analog/frontend/results/legacy_measurement_audit.json","Strict read-only reanalysis supersedes historical measurement counts without deleting old records"),
    ("frontend_frozen_candidate","analog/frontend/results/frozen_delivery.json","Same-source FDDA10 finite characterization; common-mode oscillation and static errors prevent qualification"),
    ("frontend_repair_20260910","analog/frontend/repair_20260910/repair_summary.json","Frozen-hash candidate experiments, scoped gains and explicit solver/electrical failures; no full frontend PASS"),
    ("frontend_g16_static_pvt_20260910","analog/frontend/repair_20260910/qualification_g16_pvt/20260910T065530849637Z/summary.json","All 45 G16 standalone deterministic DC cases measured: 30 accuracy PASS, 15 FAIL; not stability, sampled accuracy or three-gain full-chain qualification"),
    ("adc_static_framework_20260910","analog/adc/verification_20260910/results/20260910T063055343911Z/summary.json","Three input points and six real conversions plus runtime audit; no complete all-code static qualification"),
    ("adc_timestep_comparison_20260910","analog/adc/verification_20260910/timestep_results/20260910T063430835346Z/comparison.json","Same frozen ADC 2ns/10ns numerical comparison; global DAC waveform criterion failed, original defaults retained"),
    ("noise_engine_qualification_20260910","verification/noise_20260910/qualification.json","Intrinsic RC noise demonstrated; actual SKY130 BSIM4v5 versus installed BSIM4v8 noise mismatch prevents device qualification"),
    ("frontend_native_pole_audit_20260910","analog/frontend/repair_20260910/pole_audit/qualification.json","Two native closed-loop pole attempts returned numerically unvalidated roots; neither stability nor instability established"),
    ("frontend_closure_20260911","analog/frontend/closure_20260911/closure_summary.json","Eight bounded real-PDK frontend diagnostics; headroom repaired but same-source three-gain static and settling gates still fail"),
    ("frontend_redesign_20260911","analog/frontend/redesign_20260911/qualification.json","New same-source three-gain frontend: nominal static accuracy passes, while real-CDAC dynamic settling, formal stability and one resistor layoutability gate fail"),
    ("adc_bridge_and_fullcode_feasibility_20260911","analog/adc/closure_20260911/results/feasibility_and_bridge_report.json","Local 33-bit bridge export repair and six-conversion recheck; strict waveform and 131073-point full-code gates remain incomplete"),
    ("adc_acceleration_20260911","analog/adc/acceleration_20260911/results/delivery_report.json","Event-compressed conditional trace prediction accepts six new inputs, but strict numerical-equivalence and practical full-code runtime gates remain failed"),
    ("native_noise_closure_20260911","verification/noise_closure_20260911/qualification.json","Native SKY130 BSIM4v5 stationary-noise preservation and finite-band planning; intrinsic switching transient noise unavailable"),
    ("xyce_identity_20260911","verification/noise_closure_20260911/xyce_capability.json","Installed Xyce 7.10 identity only; current official table does not list BSIM4 stationary-noise support"),
    ("cdac_common_centroid_assignment_20260911","physical/cdac/assignment_summary.json","Deterministic 8192-active-unit P/N common-centroid placement assignment; not routed physical verification"),
    ("cdac_floorplan_20260911","physical/cdac_layout_20260911/qualification.json","Real SKY130 hierarchical 8192-active-MIM placement floorplan and placement-only DRC; routing/LVS/PEX open"),
    ("cdac_routed_macro_20260911","physical/cdac_route_20260911/qualification.json","Fully routed passive differential CDAC macro: Magic DRC, independently referenced LVS, and RC PEX; excludes switches, comparator, reference network and ADC performance"),
]


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_mapping(mapping,base):
    if not isinstance(mapping,dict):
        return {"status":"NOT_A_PATH_HASH_MAP"}
    mismatched, missing = [], []
    checked = 0
    for name,digest in mapping.items():
        if not isinstance(digest,str) or len(digest)!=64:
            continue
        path = base / name
        if not path.exists():
            missing.append(name)
        elif hash_file(path) != digest:
            mismatched.append(name)
        checked += 1
    return {"status":"MATCH" if checked and not missing and not mismatched else "MISSING_OR_CHANGED" if checked else "NO_HASH_ENTRIES",
            "checked":checked,"changed":mismatched,"missing":missing}


def main():
    entries = []
    for name,relative,scope in EVIDENCE:
        path = ROOT / relative
        row = {"id":name,"path":relative,"scope":scope,"exists":path.exists()}
        if path.exists():
            try:
                report = json.loads(path.read_text())
                row.update({"sha256":hash_file(path),"reported_status":report.get("status"),
                            "reported_evidence_level":report.get("evidence_level"),
                            "counts":report.get("counts")})
                mapping = report.get("source_sha256")
                # Digital manifests use repo-relative paths; phase reports
                # have a single source digest. Do not guess other schemas.
                if name.startswith("digital_") and isinstance(mapping,dict):
                    row["current_source_comparison"] = check_mapping(mapping,REPO)
                if name == "phase_generator":
                    row["current_phase_source_matches"] = mapping==hash_file(ROOT/"integration/sensor_phases.spice")
            except (ValueError,OSError) as error:
                row["read_error"] = str(error)
        entries.append(row)
    integration = []
    for path in sorted((ROOT/"integration/results").glob("adc_*/summary.json")):
        record = json.loads(path.read_text())
        integration.append({"path":str(path.relative_to(ROOT)),"sha256":hash_file(path),
            "status":record.get("status"),"returncode":record.get("returncode"),"arguments":record.get("arguments"),
            "raw_codes":record.get("raw_codes"),"checks":record.get("checks"),
            "scope":"Short deterministic schematic/RTL integration; not full ADC or system qualification"})
    revision = subprocess.run(["git","rev-parse","HEAD"],cwd=REPO,text=True,capture_output=True,check=True).stdout.strip()
    unchanged = subprocess.run(["git","diff","--quiet","HEAD","--",".",":(exclude)v2"],cwd=REPO).returncode==0
    report = {"generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "status":"IN_PROGRESS_WITH_OPEN_CIRCUIT_FAILURES","full_chip_qualified":False,
        "all_non_cadence_work_complete":False,"cadence":"DEFERRED_BY_USER","silicon_measured":False,
        "v1_commit":revision,"tracked_v1_unchanged":unchanged,"evidence":entries,"short_integration_runs":integration,
        "unclosed_acceptance":["One frozen full-chain candidate with all three gains",
            "45-PVT times three gains of full-system specified accuracy/power",
            "Qualified dynamic device-noise-inclusive SNDR and long coherent records",
            "All-code independent ADC INL/DNL and missing-code check",
            "Full-chain 200-real-mismatch static screen and representative dynamic reruns",
            "Fixed nominal calibration and independent complete VT holdouts",
            "Differential/common-mode loop phase margins and all boundary/interference tests",
            "Complete analog/core layout and top-level parasitic physical regression",
            "Cadence native schematic, physical closure, and common-stimulus comparison"],
        "interpretation":"This report only indexes scoped evidence. Missing or changed sources cannot inherit PASS from an older report; frozen source snapshots remain historical evidence."}
    folder = ROOT/"results/evidence_snapshots"
    folder.mkdir(exist_ok=True)
    snapshot = folder/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
    encoded = json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    snapshot.write_text(encoded)
    (ROOT/"results/project_evidence.json").write_text(encoded)
    print(json.dumps({"status":report["status"],"full_chip_qualified":False,"evidence_entries":len(entries),
                      "short_integration_runs":len(integration),"v1_unchanged":unchanged,"snapshot":str(snapshot)},indent=2))


if __name__ == "__main__":
    main()
