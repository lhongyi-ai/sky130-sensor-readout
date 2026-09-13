#!/usr/bin/env python3
"""Record installed Xyce identity without claiming a noise-circuit result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent


def run(*args: str) -> dict:
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return {
        "command": list(args),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    executable = shutil.which("Xyce")
    report = {
        "status": "IDENTITY_ONLY_NOT_NOISE_QUALIFIED",
        "executable": executable,
        "version": run("Xyce", "-v") if executable else None,
        "capabilities": run("Xyce", "-capabilities") if executable else None,
        "official_reference": {
            "url": "https://xyce.sandia.gov/download/2068/?tmstv=1754510749",
            "title": "Xyce Reference Guide, Version 7.10",
            "table": "2-36, Features Supported by Xyce Device Models",
            "review_result": "BSIM4 level 14/54 has no Y in the Stationary Noise column",
        },
        "interpretation": (
            "The installed executable identity and official feature table do not provide "
            "a BSIM4 noise path. No SKY130 Xyce circuit, switching noise, or transient "
            "noise result is claimed by this probe."
        ),
        "adc_noise_qualified": False,
    }
    if executable:
        report["executable_sha256"] = hashlib.sha256(Path(executable).read_bytes()).hexdigest()
    (HERE / "xyce_capability.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "status": report["status"],
        "executable": executable,
        "version_returncode": report["version"]["returncode"] if executable else None,
    }, indent=2))
    return 0 if executable and report["version"]["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
