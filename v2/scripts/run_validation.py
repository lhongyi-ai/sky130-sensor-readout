#!/usr/bin/env python3
"""One local entrypoint: tests, reproducible behavioral data, and digital RTL.

The authoritative validation.json is marked RUNNING before execution so a
failed/interrupted attempt cannot silently present an old PASS as current.
No Cadence, remote login, PDK probing, or network operation is performed.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
RESULTS = ROOT / "results"
EXTRA_TEST_DIRECTORIES = [
    ("adc_static_framework_tests", "analog/adc/verification_20260910"),
    ("adc_bridge_closure_tests", "analog/adc/closure_20260911"),
    ("adc_acceleration_audit_tests", "analog/adc/acceleration_20260911"),
    ("noise_qualification_audit_tests", "verification/noise_20260910"),
    ("noise_closure_tests", "verification/noise_closure_20260911"),
    ("frontend_repair_framework_tests", "analog/frontend/repair_20260910"),
    ("native_pole_audit_tests", "analog/frontend/repair_20260910/pole_audit"),
    ("frontend_closure_evidence_tests", "analog/frontend/closure_20260911"),
    ("frontend_redesign_evidence_tests", "analog/frontend/redesign_20260911"),
    ("cdac_assignment_tests", "physical/cdac"),
    ("cdac_floorplan_tests", "physical/cdac_layout_20260911"),
    ("cdac_routed_macro_tests", "physical/cdac_route_20260911"),
]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def runtime_fingerprints():
    paths = []
    for directory in ("sensor_readout", "scripts", "tests", "rtl", "config"):
        paths += [p for p in (ROOT / directory).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".v", ".sv", ".json")]
    paths += [ROOT / "requirements.txt"]
    for _, directory in EXTRA_TEST_DIRECTORIES:
        paths += list((ROOT / directory).glob("*.py"))
    paths += [ROOT / "analog/frontend" / name for name in (
        "qualify_advanced.py", "measurement_evidence.py", "measurements.py", "run_frontend.py")]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.exists()}


def main():
    report = {"status": "RUNNING", "cadence": "DEFERRED_BY_USER", "physical_chip_qualified": False,
              "m2_gate": "PARTIAL_PDK_FEASIBILITY_NOT_VERIFIED", "stages": []}
    report["runtime_source_sha256_before"] = runtime_fingerprints()
    write_json(RESULTS / "validation.json", report)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    commands = [
        ("python_tests", [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", "test_*.py", "-v"]),
        *[(name, [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / directory), "-p", "test_*.py", "-v"])
          for name, directory in EXTRA_TEST_DIRECTORIES],
        ("behavioral_experiments", [sys.executable, str(ROOT / "scripts/run_behavioral.py")]),
        ("physical_analytical_budget", [sys.executable, str(ROOT / "scripts/run_physical_budget.py")]),
        ("digital_rtl", [sys.executable, str(ROOT / "tests/rtl/run.py")]),
    ]
    failed = False
    for name, command in commands:
        try:
            result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
            stage = {"name": name, "returncode": result.returncode,
                     "stdout": result.stdout, "stderr": result.stderr}
            failed |= result.returncode != 0
            if name.endswith("_tests"):
                count = re.search(r"Ran (\d+) tests? in", result.stderr)
                stage["tests_run"] = int(count.group(1)) if count else 0
                if stage["tests_run"] == 0:
                    stage["error"] = "no Python tests discovered"
                    failed = True
            if name == "digital_rtl":
                try:
                    write_json(RESULTS / "rtl_validation.json", json.loads(result.stdout))
                except json.JSONDecodeError:
                    stage["report_parse_error"] = True
                    failed = True
        except subprocess.TimeoutExpired:
            stage = {"name": name, "returncode": None, "error": "timeout after 60 seconds"}
            failed = True
        report["stages"].append(stage)
        write_json(RESULTS / "validation.json", report)
    baseline = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", ".", ":(exclude)v2"],
                              cwd=REPO, capture_output=True, text=True)
    report["tracked_v1_unchanged_from_HEAD"] = baseline.returncode == 0
    failed |= baseline.returncode != 0
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    report["v1_baseline_commit"] = revision.stdout.strip() if revision.returncode == 0 else None
    paths = []
    for directory in ("sensor_readout", "scripts", "tests", "rtl", "config", "docs"):
        paths += [p for p in (ROOT / directory).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".v", ".sv", ".json", ".md")]
    paths += [ROOT / "README.md", ROOT / "requirements.txt"]
    report["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(paths) if p.exists()}
    report["runtime_source_sha256_after"] = runtime_fingerprints()
    report["runtime_sources_stable_during_run"] = (
        report["runtime_source_sha256_before"] == report["runtime_source_sha256_after"])
    failed |= not report["runtime_sources_stable_during_run"]
    report["status"] = "FAIL" if failed else "LOCAL_MODEL_AND_DIGITAL_TESTS_PASS"
    report["total_python_tests_run"] = sum(stage.get("tests_run", 0) for stage in report["stages"])
    write_json(RESULTS / "validation.json", report)
    print(json.dumps({"status": report["status"], "m2_gate": report["m2_gate"],
                      "physical_chip_qualified": False, "tracked_v1_unchanged": report["tracked_v1_unchanged_from_HEAD"],
                      "report": str(RESULTS / "validation.json")}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
