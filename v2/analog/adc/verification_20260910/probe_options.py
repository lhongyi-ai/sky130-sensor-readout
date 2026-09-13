#!/usr/bin/env python3
"""Load the frozen circuit and print solver options without transient or OP."""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import subprocess

from static_campaign import HERE, sha, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-op", action="store_true", help="initialize the circuit with OP before printing effective options")
    args = parser.parse_args()
    baseline = HERE / "timestep_results/20260910T063430835346Z/maxstep_2ns"
    old_summary = json.loads((baseline / "summary.json").read_text())
    source = baseline / "adc.spice"
    if sha(source) != old_summary["artifact_sha256"]["adc.spice"]:
        raise ValueError("frozen baseline changed")
    text = source.read_text()
    head, control = text.split(".control\n", 1)
    if control.count(".endc") != 1:
        raise ValueError("unexpected control block")
    out = HERE / "option_probes" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True)
    (out / "probe.spice").write_text(head + ".control\n" + ("op\n" if args.after_op else "") + "option\nquit\n.endc\n.end\n")
    (out / ".spiceinit").write_bytes((baseline / ".spiceinit").read_bytes())
    proc = subprocess.run(["ngspice", "-b", "-o", "native.log", "probe.spice"], cwd=out,
                          env=dict(os.environ, SPICE_USERINIT_DIR=str(out)), capture_output=True, text=True, timeout=60)
    log = proc.stdout + proc.stderr
    if (out / "native.log").exists():
        log += (out / "native.log").read_text(errors="replace")
    (out / "probe.log").write_text(log)
    write_json(out / "summary.json", {"status": "READ_ONLY_OPTIONS_PROBE", "returncode": proc.returncode,
        "baseline_deck_sha256": sha(source), "probe_sha256": sha(out / "probe.spice"),
        "transient_requested": False, "operating_point_requested": args.after_op, "complete_adc_qualified": False})
    print(log)
    print("PROBE_DIRECTORY=" + str(out))


if __name__ == "__main__":
    main()
