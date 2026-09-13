#!/usr/bin/env python3
"""Audit the full grid and publish a portable, explicitly scoped switch release."""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
from pathlib import Path
import shutil

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    physical=json.loads((HERE/"results/dummy_layout_final.json").read_text())
    result_path=HERE/"results/dummy_w4w8_rc_full.json"
    result=json.loads(result_path.read_text())
    boundary_path=HERE/"results/dummy_fullscale_boundaries.json"
    boundary=json.loads(boundary_path.read_text())
    run=HERE/"runs"/result["run_tag"]
    layout=HERE/"artifacts/dummy_layout_final"
    source=HERE/"candidates/adc_tgate_dual_lvt_dummy.spice"
    for path in (run/"candidate.spice", source):
        if digest(path)!=result["source_sha256"][str(source.relative_to(ROOT))]:
            raise RuntimeError("Candidate source differs from the qualified netlist")
    if digest(run/"adc_tgate_flat.rc.spice") != physical["artifact_sha256"]["adc_tgate_flat.rc.spice"]:
        raise RuntimeError("Qualification RC is not the frozen physically checked RC")
    expected=set(itertools.product(("tt","ff","ss","fs","sf"),(1.62,1.8,1.98),
        (-20,27,85),(-.2,0,.2),(0,350,1000),(-.05,0,.05),("schematic","layout_rc")))
    observed=[]
    for row in result["results"]:
        delta=round(row["input_v"]-row["vdd_v"]/2-row["commonmode_shift_v"],8)
        observed.append((row["corner"],row["vdd_v"],row["temperature_c"],delta,
            row["source_ohm"],row["commonmode_shift_v"],row["view"]))
    checks={"full_grid_exactly_once":len(observed)==len(expected) and set(observed)==expected,
        "drc_zero":physical["magic_drc_count"]==0,
        "lvs_unique":physical["netgen_lvs"]=="unique_match",
        "positive_rc_network":physical["extracted_resistors"]>0 and physical["extracted_capacitors"]>0,
        "acquisition_duration_matches_measured_conservative_bound":result["acquisition_ns"]==2476.847754,
        "all_required_and_sensitivity_cases_pass":result["failed_cases"]==0,
        "all_raw_acquisition_values_pass":all(abs(r["acquisition_error_v"])<=.8/4096/4 for r in result["results"]),
        "all_raw_held_values_pass":all(abs(r["end_hold_error_v"])<=.8/4096/4 for r in result["results"])}
    checks["opposite_fullscale_boundary_216_cases_pass"]=(boundary["view_cases"]==216 and boundary["failed_cases"]==0
        and boundary["source_qualification_sha256"]==digest(result_path))
    if not checks["full_grid_exactly_once"]:
        raise RuntimeError("Missing, duplicated or unexpected qualification points")
    # Recompute acceptance values from every retained waveform, not only the
    # summary booleans. Incomplete transient output must never pass by interp's
    # out-of-range endpoint behavior.
    for batch in range(45):
        paths=list(run.glob(f"batch_{batch:02d}_*.tsv"))
        if len(paths)!=1:
            raise RuntimeError("Expected one raw waveform for every PVT batch")
        values=np.loadtxt(paths[0],skiprows=1)
        if values.shape[1]!=55 or not np.isfinite(values).all() or values[-1,0]<10e-6-1e-14 or not np.all(np.diff(values[:,0])>0):
            raise RuntimeError("Incomplete, nonfinite or malformed transient data")
        for row in (r for r in result["results"] if r["batch"]==batch):
            actual=np.interp(result["acquisition_measurement_ns"]*1e-9,values[:,0],values[:,row["column"]])-row["input_v"]
            held=values[-1,row["column"]]-row["input_v"]
            if not np.isclose(actual,row["acquisition_error_v"],rtol=0,atol=1e-14) or not np.isclose(held,row["end_hold_error_v"],rtol=0,atol=1e-14):
                raise RuntimeError("Reported metrics differ from raw waveform")
    checks["all_45_raw_waveforms_complete_and_metrics_recomputed"]=True
    evidence=HERE/"evidence/final_qualification"
    evidence.mkdir(parents=True,exist_ok=True)
    files=[]
    # Retain every final raw waveform, not merely selected passing examples.
    paths=[(p,evidence) for p in sorted(run.iterdir())]
    boundary_evidence=HERE/"evidence/fullscale_boundaries"
    boundary_evidence.mkdir(parents=True,exist_ok=True)
    paths += [(p,boundary_evidence) for p in sorted((HERE/"runs/dummy_fullscale_boundaries").iterdir())]
    for path,destination in paths:
        if path.suffix==".tsv":
            dest=destination/(path.name+".gz")
            with path.open("rb") as inp, dest.open("wb") as out:
                with gzip.GzipFile(filename="",fileobj=out,mode="wb",mtime=0) as compressed:
                    shutil.copyfileobj(inp,compressed)
            files.append({"file":str(dest.relative_to(HERE)),"sha256":digest(dest),"raw_sha256":digest(path)})
        elif path.suffix in (".spice",".log",".py"):
            dest=destination/path.name
            shutil.copy2(path,dest)
            files.append({"file":str(dest.relative_to(HERE)),"sha256":digest(dest)})
    worst=[]
    for view in ("schematic","layout_rc"):
        rows=[r for r in result["results"] if r["view"]==view]
        for key in ("acquisition_error_v","end_hold_error_v","off_input_feedthrough_v","late_hold_droop_v"):
            row=max(rows,key=lambda r:abs(r[key]))
            worst.append({"view":view,"metric":key,"absolute_value_uv":abs(row[key])*1e6,"case":row})
    report={"status":"STANDALONE_SAMPLING_SWITCH_QUALIFIED" if all(checks.values()) else "FAILED_SPECIFICATION",
        "scope":"Dedicated input sampling TG with half-width dummy compensation; not a generic reference switch.",
        "cadence_used":False,"whole_adc_validated":False,"silicon_measured":False,
        "checks":checks,"pvt_combinations":45,"case_pairs":1215,"simulated_view_cases":2430,
        "required_source_ohm":350,"sensitivity_source_ohm":[0,1000],"commonmode_offsets_v":[-.05,0,.05],
        "acquisition_ns":result["acquisition_ns"],"hold_interval_ns":result["hold_interval_ns"],
        "load_f":result["load_f"],"quarter_lsb_uv":.8/4096/4*1e6,
        "frozen_interface":{"ports":["A","B","EN","ENB","VDD","VSS"],
            "A":"Driven acquisition source/reference side","B":"Held/CDAC-top-plate side; dummy diffusions short only to B",
            "EN":"Rail clock high during acquisition","ENB":"Complement of EN",
            "schematic_file":"candidates/adc_tgate_dual_lvt_dummy.spice",
            "schematic_subckt":"adc_tgate_dual_lvt_dummy",
            "schematic_instance":"XSAMPLE source held en enb vdd vss adc_tgate_dual_lvt_dummy",
            "parameters":{"WN_um":4,"LN_um":.15,"WP_um":8,"LP_um":.35,"dummy_width_ratio":.5},
            "rc_file":"artifacts/dummy_layout_final/adc_tgate_flat.rc.spice","rc_subckt":"adc_tgate_flat",
            "gds_file":"artifacts/dummy_layout_final/adc_tgate_layout.gds","gds_top_cell":"adc_tgate_layout",
            "import_note":"Use only the final GDS/RC; historical alternatives reuse demonstration cell names and must not be merged together."},
        "layout":{"bbox_um":physical["bbox_um"],"bbox_area_um2":physical["bbox_area_um2"],
            "resistors":physical["extracted_resistors"],"capacitors":physical["extracted_capacitors"]},
        "opposite_fullscale_boundary":{"pvt_count":4,"view_cases":216,"failed_cases":boundary["failed_cases"],
            "max_acquisition_error_uv":max(abs(r["acquisition_error_v"]) for r in boundary["results"])*1e6,
            "max_final_hold_error_uv":max(abs(r["end_hold_error_v"]) for r in boundary["results"])*1e6,
            "qualification_sha256":digest(boundary_path)},
        "worst_cases":worst,"limitations":result["limitations"]+[
            "The resistance here is a standalone Thevenin driver at the sampler input, not a model of sensor impedance propagated through the PGA closed loop.",
            "The nominal 0ohm sensitivity case uses 0.001ohm in SPICE for numerical regularization.",
            "Full system must verify the real two-leg clock loading/skew; this sweep applies ideal rail clocks with the measured conservative acquisition duration.",
            "This does not qualify small CDAC reference TGs, comparator, PGA, full-ADC static/dynamic performance or noise."],
        "candidate_sha256":digest(source),"rc_sha256":digest(layout/"adc_tgate_flat.rc.spice"),
        "gds_sha256":digest(layout/"adc_tgate_layout.gds"),"qualification_sha256":digest(result_path),
        "render_sha256":digest(layout/"adc_tgate_layout.png"),
        "release_script_sha256":digest(Path(__file__)),"portable_evidence":files}
    (HERE/"results/sampling_switch_release.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("portable_evidence","worst_cases")},indent=2))
    return 0 if all(checks.values()) else 1


if __name__=="__main__":
    raise SystemExit(main())
