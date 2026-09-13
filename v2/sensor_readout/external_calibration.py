"""Apply the frozen three-point external calibration to imported raw records.

Records may come from a model or circuit simulator. The functions do not
upgrade their evidence level or infer missing voltage/temperature/instance IDs.
"""
from collections import defaultdict
import math
import numpy as np
from .analysis import fit_calibration, apply_calibration

LSB = 0.8 / 4096
TRAIN_FRACTIONS = (-0.8, 0.0, 0.8)


def normalize_records(records, require_known_input=False):
    rows, ids = [], set()
    for record in records:
        row = dict(record)
        for field in ("instance_id", "sample_id", "gain", "vdd_v", "temperature_c", "raw_code"):
            if field not in row or str(row[field]).strip() == "":
                raise ValueError(f"missing raw record field: {field}")
        for field in ("instance_id", "sample_id"):
            row[field] = str(row[field])
            if any(ord(c) < 32 for c in row[field]):
                raise ValueError(f"control character in {field}")
        if row["sample_id"] in ids:
            raise ValueError("sample_id must be unique within the imported dataset")
        ids.add(row["sample_id"])
        for field in ("gain", "raw_code"):
            if isinstance(row[field], bool):
                raise ValueError(f"{field} must not be boolean")
            value = float(row[field])
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError(f"{field} must be an integer")
            row[field] = int(value)
        if row["gain"] not in (1, 4, 16) or not 0 <= row["raw_code"] <= 4095:
            raise ValueError("unsupported gain or raw code outside 12-bit range")
        for field in ("vdd_v", "temperature_c"):
            row[field] = float(row[field])
            if not math.isfinite(row[field]):
                raise ValueError(f"nonfinite {field}")
        if row["vdd_v"] <= 0 or row["temperature_c"] <= -273.15:
            raise ValueError("unphysical voltage/temperature metadata")
        vin = row.get("sensor_input_v", "")
        if vin is not None and str(vin).strip() != "":
            row["sensor_input_v"] = float(vin)
            if not math.isfinite(row["sensor_input_v"]):
                raise ValueError("nonfinite known sensor input")
        elif require_known_input:
            raise ValueError("calibration/validation requires known sensor_input_v")
        else:
            row["sensor_input_v"] = None
        rows.append(row)
    if not rows:
        raise ValueError("empty dataset")
    return rows


def coefficient_key(instance_id, gain):
    # JSON objects use explicit records, never delimiter-composed identities.
    return instance_id, gain


def fit_records(records):
    rows = normalize_records(records, require_known_input=True)
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["vdd_v"] != 1.8 or row["temperature_c"] != 27.0:
            raise ValueError("fit only at 1.8 V and 27 C; corner data must use frozen coefficients")
        fraction = row["sensor_input_v"] * row["gain"] / 0.4
        matching = [f for f in TRAIN_FRACTIONS if abs(fraction-f) < 1e-10]
        if len(matching) != 1:
            raise ValueError("only -80%, 0, +80% full scale may be used for fitting")
        if row["raw_code"] in (0, 4095):
            raise ValueError("individual clipped training sample; averaging must not hide clipping")
        groups[coefficient_key(row["instance_id"], row["gain"])][matching[0]].append(row["raw_code"])
    coefficients = []
    for (instance, gain), points in sorted(groups.items()):
        if set(points) != set(TRAIN_FRACTIONS) or any(len(points[f]) < 4096 for f in TRAIN_FRACTIONS):
            raise ValueError("each instance/gain needs all three training points, >=4096 samples each")
        means = [float(np.mean(points[f])) for f in TRAIN_FRACTIONS]
        expected = [(0.4*f+0.4)/LSB-0.5 for f in TRAIN_FRACTIONS]
        coefficient = fit_calibration(means, expected, gain, instance)
        coefficient["training_fractions"] = list(TRAIN_FRACTIONS)
        coefficient["training_counts"] = [len(points[f]) for f in TRAIN_FRACTIONS]
        coefficient["training_sample_stdev_lsb"] = [float(np.std(points[f], ddof=1)) for f in TRAIN_FRACTIONS]
        coefficients.append(coefficient)
    return {"schema": "sky130_external_calibration_set_v1", "scope": "external_software_not_on_chip",
            "evidence_verified_by_importer": False, "coefficients": coefficients}


def _coefficient_index(bundle):
    if not isinstance(bundle, dict) or bundle.get("schema") != "sky130_external_calibration_set_v1":
        raise ValueError("unsupported calibration-set schema")
    index = {}
    for coefficient in bundle.get("coefficients", []):
        # Existing scalar calibration implementation rechecks fit provenance.
        apply_calibration([2048], coefficient)
        key = coefficient_key(coefficient["instance_id"], coefficient["gain"])
        if key in index:
            raise ValueError("duplicate coefficient identity")
        if coefficient.get("training_fractions") != list(TRAIN_FRACTIONS):
            raise ValueError("missing frozen training-point provenance")
        expected = [(0.4*f+0.4)/LSB-0.5 for f in TRAIN_FRACTIONS]
        if not np.allclose(coefficient["expected_codes"], expected, rtol=0, atol=1e-10):
            raise ValueError("expected code coordinates do not match frozen training points")
        counts = coefficient.get("training_counts", [])
        if len(counts) != 3 or any(not isinstance(c, int) or c < 4096 for c in counts):
            raise ValueError("invalid training sample-count provenance")
        index[key] = coefficient
    if not index:
        raise ValueError("no coefficients")
    return index


def apply_records(records, bundle):
    rows = normalize_records(records)
    index = _coefficient_index(bundle)
    for row in rows:
        key = coefficient_key(row["instance_id"], row["gain"])
        if key not in index:
            raise ValueError(f"no nominal calibration for instance/gain {key}")
        # _coefficient_index already validates every coefficient and its fit.
        coefficient = index[key]
        corrected = float(coefficient["slope"]*row["raw_code"] + coefficient["intercept"])
        row["corrected_code_float"] = corrected
        row["estimated_sensor_input_v"] = ((corrected+0.5)*LSB-0.4)/row["gain"]
        row["raw_at_rail"] = row["raw_code"] in (0, 4095)
    return rows


def validate_records(records, bundle):
    rows = normalize_records(records, require_known_input=True)
    groups = defaultdict(list)
    for row in apply_records(rows, bundle):
        fraction = row["sensor_input_v"]*row["gain"]/0.4
        if abs(fraction) >= 1:
            raise ValueError("static holdout must be inside full scale")
        if any(abs(fraction-f) < 1e-10 for f in TRAIN_FRACTIONS):
            raise ValueError("holdout reuses a training input point")
        key = (row["instance_id"], row["gain"], row["vdd_v"], row["temperature_c"], row["sensor_input_v"])
        groups[key].append(row)
    result = []
    for (instance, gain, vdd, temp, vin), samples in sorted(groups.items()):
        expected = (gain*vin+0.4)/LSB-0.5
        error = np.array([r["corrected_code_float"]-expected for r in samples])
        limit = 1.0 if vdd == 1.8 and temp == 27.0 else 4.0
        enough = len(samples) >= 2048
        clipped = sum(r["raw_at_rail"] for r in samples)
        mean = float(np.mean(error))
        result.append({"instance_id": instance, "gain": gain, "vdd_v": vdd, "temperature_c": temp,
            "sensor_input_v": vin, "sample_count": len(samples), "clipped_count": clipped,
            "mean_static_residual_lsb": mean, "sample_stdev_lsb": float(np.std(error, ddof=1)) if len(samples)>1 else None,
            "mean_residual_limit_lsb": limit, "sample_count_sufficient": enough,
            "status": "PASS" if enough and clipped == 0 and abs(mean) <= limit else "FAIL"})
    return {"status": "PROVIDED_HOLDOUT_POINTS_PASS" if all(r["status"] == "PASS" for r in result) else "FAIL",
        "complete_pvt_matrix_verified": False, "chip_qualified": False,
        "coefficients_refitted": False, "test_points": result,
        "warning": "This report covers only supplied points. It does not prove full PVT, dynamic precision, noise, or physical evidence provenance."}
