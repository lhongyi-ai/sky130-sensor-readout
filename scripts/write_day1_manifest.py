#!/usr/bin/env python3
"""Write a compact provenance and checksum manifest for a completed Day 1 run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "day1"
GENERATED = ROOT / "results" / "generated" / "day1"
MANIFEST = ROOT / "results" / "day1_reproducibility_manifest.json"
LENGTH_TAGS = ("0p15", "0p3", "0p5", "0p8", "1")
ACCEPTED_LOG_WARNING = (
    "Warning: m=xx on .subckt line will override multiplier m hierarchy!"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_checksums(paths: list[Path]) -> dict[str, str]:
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Cannot write Day 1 manifest; missing: {missing}")
    return {
        str(path.relative_to(ROOT)): sha256(path)
        for path in sorted(paths, key=lambda item: str(item.relative_to(ROOT)))
    }


def parse_identity(path: Path) -> dict[str, str]:
    identity: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and value:
            identity[key] = value
    required = {
        "container_architecture",
        "container_python",
        "container_ngspice",
        "pdk_model_deck",
        "pdk_model_deck_sha256",
    }
    missing = sorted(required - identity.keys())
    if missing:
        raise ValueError(f"Incomplete container identity file; missing keys: {missing}")
    return identity


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def validate_logs(paths: list[Path]) -> dict[str, object]:
    accepted_warning_count = 0
    fatal_pattern = re.compile(
        r"fatal|singular matrix|no convergence|timestep too small|aborted",
        flags=re.IGNORECASE,
    )
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.count("No. of Data Rows : 181") != 1:
            raise ValueError(f"Missing or duplicate 181-row completion marker in {path}")
        if text.count("ngspice-47 done") != 1:
            raise ValueError(f"Missing or duplicate ngspice completion marker in {path}")
        if fatal_pattern.search(text):
            raise ValueError(f"Fatal simulator diagnostic found in {path}")
        warnings = [line.strip() for line in text.splitlines() if line.startswith("Warning:")]
        unexpected = [warning for warning in warnings if warning != ACCEPTED_LOG_WARNING]
        if unexpected:
            raise ValueError(f"Unexpected simulator warning in {path}: {unexpected}")
        accepted_warning_count += warnings.count(ACCEPTED_LOG_WARNING)
    return {
        "status": "PASS",
        "logs_checked": len(paths),
        "expected_rows_per_log": 181,
        "accepted_warning": ACCEPTED_LOG_WARNING,
        "accepted_warning_occurrences": accepted_warning_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-reference", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--docker-client-version", required=True)
    parser.add_argument("--docker-server-version", required=True)
    args = parser.parse_args()

    identity_path = RAW / "container_tool_identity.txt"
    identity = parse_identity(identity_path)
    revision_match = re.search(r"/versions/([^/]+)/", identity["pdk_model_deck"])
    pdk_revision = revision_match.group(1) if revision_match else "UNRESOLVED_FROM_PATH"

    input_paths = [
        ROOT / "netlists" / "day1" / "nfet_characterization.spice.in",
        ROOT / "netlists" / "day1" / "pfet_characterization.spice.in",
        ROOT / "netlists" / "day1" / "nmos_current_mirror.spice.in",
        ROOT / "scripts" / "render_netlists.py",
        ROOT / "scripts" / "analyze_day1.py",
        ROOT / "scripts" / "run_day1.sh",
        ROOT / "scripts" / "write_day1_manifest.py",
    ]
    rendered_paths = [
        GENERATED / f"{device}_characterization_l{tag}.spice"
        for device in ("nfet", "pfet")
        for tag in LENGTH_TAGS
    ] + [GENERATED / "nmos_current_mirror.spice"]
    log_paths = [
        RAW / f"{device}_characterization_l{tag}.log"
        for device in ("nfet", "pfet")
        for tag in LENGTH_TAGS
    ] + [RAW / "nmos_current_mirror.log"]
    output_paths = [
        RAW / f"{device}_characterization_l{tag}.{suffix}"
        for device in ("nfet", "pfet")
        for tag in LENGTH_TAGS
        for suffix in ("tsv", "log")
    ] + [
        RAW / "nmos_current_mirror.tsv",
        RAW / "nmos_current_mirror.log",
        identity_path,
        ROOT / "results" / "device_sizing_candidates.csv",
        ROOT / "results" / "current_mirror_summary.csv",
        ROOT / "results" / "plots" / "day1_device_characterization.png",
        ROOT / "results" / "plots" / "day1_current_mirror_compliance.png",
    ]

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "simulation_conditions": {
            "corner": "tt",
            "temperature_c": 27,
            "sweep_start_v": 0.0,
            "sweep_stop_v": 1.8,
            "sweep_step_v": 0.01,
            "points_per_sweep": 181,
        },
        "container": {
            "requested_image_reference": args.image_reference,
            "local_image_id": args.image_id,
            "architecture": identity["container_architecture"],
            "docker_client_version": args.docker_client_version,
            "docker_server_version": args.docker_server_version,
            "python": identity["container_python"],
            "ngspice": identity["container_ngspice"],
        },
        "pdk": {
            "revision": pdk_revision,
            "model_deck": identity["pdk_model_deck"],
            "model_deck_sha256": identity["pdk_model_deck_sha256"],
        },
        "host_analysis": {
            "platform": platform.platform(),
            "python": sys.version.splitlines()[0],
            "numpy": package_version("numpy"),
            "pandas": package_version("pandas"),
            "matplotlib": package_version("matplotlib"),
        },
        "log_validation": validate_logs(log_paths),
        "sha256": {
            "authored_inputs": relative_checksums(input_paths),
            "rendered_netlists": relative_checksums(rendered_paths),
            "run_outputs": relative_checksums(output_paths),
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST}")


if __name__ == "__main__":
    main()
