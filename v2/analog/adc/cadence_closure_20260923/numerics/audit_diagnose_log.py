#!/usr/bin/env python3
"""Summarize actual Spectre diagnosis without copying tool/license metadata."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


def audit(path):
    raw = path.read_bytes()
    s = raw.decode()
    time = None
    counts = Counter()
    bytime = defaultdict(Counter)
    devices = defaultdict(Counter)
    records = []
    for lineno, line in enumerate(s.splitlines(), 1):
        t = re.match(r"Warning from spectre at time = (.*?) during transient", line)
        if t:
            time = t[1]
        m = re.match(r"\s+WARNING \(([^)]+)\): (.*)", line)
        if not m:
            continue
        code, msg = m.groups()
        counts[code] += 1
        bytime[code][time] += 1
        device = None
        if code == "AHDLLINT-8014":
            n = re.search(r"0: (\S+): The static", msg)
            if n:
                device = n[1]
        elif code == "SPECTRE-16780":
            n = re.search(r"signal: (.*?)\. Check", msg)
            if n:
                device = n[1]
        if device:
            devices[code][device] += 1
        records.append({"line": lineno, "code": code, "time_text": time, "device": device})
    fields = {
        "accepted_steps": r"Total Number of Accepted steps\s*:\s*(\d+)",
        "LTE_rejected_steps": r"Number of LTE rejected steps\s*:\s*(\d+)",
        "Newton_rejected_steps": r"Number of Newton rejected steps\s*:\s*(\d+)",
        "minimum_accepted_step_s": r"Minimum time step\s*=\s*([\d.e+-]+)",
        "drastic_step_size_changes": r"Number of drastic step size changes\s*=\s*(\d+)",
        "recovery_steps": r"Number of steps to recover from drastic step size drop\s*=\s*(\d+)",
    }
    statistics = {}
    for key, pattern in fields.items():
        m = re.search(pattern, s)
        statistics[key] = float(m[1]) if m and key.endswith("_s") else int(m[1]) if m else None
    summary = re.search(r"spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?", s)
    return {
        "source_path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
        "simulator_summary": dict(zip(["errors", "warnings", "notices"], map(int, summary.groups()))) if summary else None,
        "warning_counts": dict(counts),
        "warning_time_counts": {k: dict(v) for k, v in bytime.items()},
        "warning_device_counts": {k: dict(v) for k, v in devices.items()},
        "warning_records": records, "statistics": statistics,
        "further_warning_suppression": "Further occurrences of this warning will be suppressed" in s,
        "suppressed_warning_total": sum(map(int, re.findall(r"^\s+(\d+) warnings suppressed\.", s, re.M))),
        "LTE_control_failure_observed": any(counts[c] for c in ["SPECTRE-16266", "SPECTRE-16578", "SPECTRE-16780"]),
        "accuracy_pass": False,
        "accuracy_pass_note": "This log-only audit never grants waveform accuracy qualification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("output", type=Path)
    a = parser.parse_args()
    r = audit(a.log)
    a.output.write_text(json.dumps(r, indent=2) + "\n")
    print(json.dumps({k: r[k] for k in ["simulator_summary", "warning_counts", "statistics", "LTE_control_failure_observed"]}, indent=2))
