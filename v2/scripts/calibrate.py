#!/usr/bin/env python3
"""CSV entrypoint for external calibration of model or circuit raw data."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sensor_readout.external_calibration import fit_records, apply_records, validate_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fit", "apply", "validate"))
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--coefficients", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new name to preserve prior evidence")
    if args.action != "fit" and args.coefficients is None:
        parser.error("apply/validate require --coefficients from one nominal fit")
    with args.input_csv.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    coefficient_data = json.loads(args.coefficients.read_text()) if args.coefficients else None
    try:
        result = {"fit": lambda: fit_records(rows), "apply": lambda: apply_records(rows, coefficient_data),
                  "validate": lambda: validate_records(rows, coefficient_data)}[args.action]()
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.action == "apply":
        # Original columns/values and raw code are retained next to correction.
        with args.output.open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result[0]))
            writer.writeheader()
            writer.writerows(result)
    else:
        result["input_sha256"] = hashlib.sha256(args.input_csv.read_bytes()).hexdigest()
        if args.coefficients:
            result["coefficient_file_sha256"] = hashlib.sha256(args.coefficients.read_bytes()).hexdigest()
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(f"{args.action}: {args.output}")
    return 1 if args.action == "validate" and result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
