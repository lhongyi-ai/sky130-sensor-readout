#!/usr/bin/env python3
"""Fail closed before any long all-code job is considered."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
KNOWN = HERE / "results/20260911T082551662858Z_known/summary.json"
PREDICTED = HERE / "results/20260911T083114860787Z_predicted/summary.json"


def evaluate_gate():
    known = json.loads(KNOWN.read_text())
    predicted = json.loads(PREDICTED.read_text())
    numeric = known.get("status") == "BOUNDED_EQUIVALENCE_PASS"
    prediction = predicted.get("status") == "PREDICTED_TRACE_ACCEPTED"
    return {
        "numeric_equivalence_0_05_lsb_pass": numeric,
        "independent_prediction_72_of_72_pass": prediction,
        "long_all_code_campaign_allowed": numeric and prediction,
        "reason": (
            "All prerequisites pass."
            if numeric and prediction
            else "The event-PWL full-waveform numerical equivalence gate failed; a correct finite predicted trace cannot override it."
        ),
        "complete_adc_qualified": False,
    }


def main():
    report = evaluate_gate()
    print(json.dumps(report, indent=2))
    return 0 if report["long_all_code_campaign_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
