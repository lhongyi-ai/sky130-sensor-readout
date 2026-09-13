#!/usr/bin/env python3
"""Hash the final human- and machine-readable dynamic-closure delivery."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FILES = (
    "candidate_06.spice",
    "sampling_switch.spice",
    "qualification.json",
    "README.md",
    "build_qualification.py",
    "run_diagnostic.py",
    "run_loop_qualification.py",
    "test_evidence.py",
    "diagnostics/07_20260911T085157880653Z_candidate_06/evidence_manifest.json",
    "diagnostics/08_20260911T085257873008Z_candidate_06_loops/evidence_manifest.json",
)


def main() -> None:
    entries = {}
    for name in FILES:
        path = HERE / name
        entries[name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    result = {
        "version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Delivery integrity only; qualification truth remains in qualification.json.",
        "files": entries,
    }
    (HERE / "delivery_manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
