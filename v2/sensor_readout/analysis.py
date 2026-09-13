"""Transparent analysis for the V2 *behavioral* readout experiments.

These functions measure supplied samples; they do not establish transistor-level
ENOB, manufacturing yield, or silicon performance. FFT inputs must already be
settled, uniformly sampled, and coherent. No window, harmonic removal from SNDR,
calibration clipping, or automatic rounding is hidden in this module.
"""

from __future__ import annotations

import math
from numbers import Integral, Real

import numpy as np


_BITS = 12
_MAX_CODE = (1 << _BITS) - 1
_CALIBRATION_SCHEMA = "sensor_readout.affine_calibration.v1"


def _finite_scalar(value: object, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _vector(values: object, name: str, minimum: int = 1) -> np.ndarray:
    source = np.asarray(values)
    if source.dtype.kind not in "iuf" or source.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional real numeric array")
    result = source.astype(float)
    if result.size < minimum or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain at least {minimum} finite values")
    return result


def spectrum_metrics(
    samples: object, sample_rate_hz: float, fundamental_bin: int
) -> dict:
    """Measure a coherent record with a rectangular, one-sided real FFT.

    DC is removed. SNDR includes *every* other positive-frequency bin, including
    aliased harmonics and Nyquist. SNR excludes the distinct aliases of harmonics
    2 through 5; THD includes those aliases. Aliases landing at DC or the
    fundamental cannot be independently resolved and are reported, not counted
    twice. SFDR considers all nonfundamental bins, not only harmonic bins.

    Even-length Nyquist power has weight one; other positive-frequency powers
    have weight two. Odd records have no Nyquist bin. Ratios are calculated after
    amplitude normalization to avoid overflow/underflow. Constant inputs and
    records without measurable noise plus distortion are rejected instead of
    returning infinite SNDR. If noise or harmonic power alone is indistinguishable
    from roundoff, its individual metric is None with an explicit reason; valid
    SNDR and SFDR are preserved. Numerical roundoff is never reported as a measured
    noise or harmonic floor.
    """
    values = _vector(samples, "samples", 8)
    fs = _finite_scalar(sample_rate_hz, "sample_rate_hz")
    if fs <= 0:
        raise ValueError("sample_rate_hz must be positive")
    size = int(values.size)
    if isinstance(fundamental_bin, (bool, np.bool_)) or not isinstance(
        fundamental_bin, Integral
    ):
        raise ValueError("fundamental_bin must be an integer")
    fundamental = int(fundamental_bin)
    last_non_nyquist = (size - 1) // 2
    if not 1 <= fundamental <= last_non_nyquist:
        raise ValueError("fundamental_bin must exclude DC and Nyquist")

    scale = float(np.max(np.abs(values)))
    if scale == 0:
        raise ValueError("samples contain no AC signal")
    centered = values / scale
    centered -= np.mean(centered)
    ac_scale = float(np.max(np.abs(centered)))
    if ac_scale == 0:
        raise ValueError("samples contain no AC signal")
    spectrum = np.fft.rfft(centered / ac_scale) / size
    powers = np.abs(spectrum) ** 2
    powers[1:] *= 2.0
    if size % 2 == 0:
        powers[-1] *= 0.5
    powers[0] = 0.0

    signal_power = float(powers[fundamental])
    all_other = powers.copy()
    all_other[fundamental] = 0.0
    nondc_power = float(np.sum(powers))
    # A numerical validity guard, not an instrument/ADC noise-floor correction.
    numerical_floor = 64.0 * np.finfo(float).eps**2 * size * nondc_power
    if signal_power <= numerical_floor:
        raise ValueError("fundamental power is absent or at numerical roundoff")

    aliases = {}
    unresolvable = []
    harmonic_bins = set()
    for order in range(2, 6):
        wrapped = (order * fundamental) % size
        alias_bin = min(wrapped, size - wrapped)
        aliases[str(order)] = int(alias_bin)
        if alias_bin in (0, fundamental):
            unresolvable.append(order)
        else:
            harmonic_bins.add(alias_bin)
    harmonic_power = float(sum(powers[index] for index in harmonic_bins))
    noise_bins = all_other.copy()
    for index in harmonic_bins:
        noise_bins[index] = 0.0
    noise_power = float(np.sum(noise_bins))
    noise_and_distortion = float(np.sum(all_other))
    spur_power = float(np.max(all_other))
    for name, power in (
        ("noise plus distortion", noise_and_distortion),
        ("largest spur", spur_power),
    ):
        if not math.isfinite(power) or power <= numerical_floor:
            raise ValueError(f"{name} power is absent or at numerical roundoff")

    def relative_db(numerator: float, denominator: float) -> float:
        return float(10.0 * (math.log10(numerator) - math.log10(denominator)))

    sndr = relative_db(signal_power, noise_and_distortion)
    unavailable = {}
    if noise_power <= numerical_floor:
        snr = None
        unavailable["snr_db"] = "noise power is absent or at numerical roundoff"
    else:
        snr = relative_db(signal_power, noise_power)
    if harmonic_power <= numerical_floor:
        thd = None
        unavailable["thd_db"] = "harmonics 2 through 5 power is absent or at numerical roundoff"
    else:
        thd = relative_db(harmonic_power, signal_power)
    return {
        "sndr_db": sndr,
        "enob": float((sndr - 1.76) / 6.02),
        "sfdr_db": relative_db(signal_power, spur_power),
        "snr_db": snr,
        "thd_db": thd,
        "metric_unavailable_reasons": unavailable,
        "sample_count": size,
        "sample_rate_hz": fs,
        "fundamental_bin": fundamental,
        "fundamental_hz": float(fs * fundamental / size),
        "harmonic_orders_max": 5,
        "harmonic_alias_bins": aliases,
        "counted_harmonic_bins": sorted(int(item) for item in harmonic_bins),
        "unresolvable_harmonic_orders": unresolvable,
        "window": "rectangular_coherent",
        "dc_removed": True,
        "enob_definition": "(SNDR_dB - 1.76) / 6.02; no amplitude correction",
    }


def _calibration_inputs(
    raw_means: object,
    expected_codes: object,
    gain: int,
    instance_id: str,
    vdd_v: float,
    temperature_c: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    raw = _vector(raw_means, "raw_means")
    expected = _vector(expected_codes, "expected_codes")
    if raw.size != 3 or expected.size != 3:
        raise ValueError("calibration requires exactly three averaged points")
    if np.unique(raw).size != 3 or np.unique(expected).size != 3:
        raise ValueError("calibration points must be distinct on both axes")
    if np.any(raw <= 0) or np.any(raw >= _MAX_CODE):
        raise ValueError("raw calibration means must not be saturated at a rail")
    if np.any(expected <= -0.5) or np.any(expected >= _MAX_CODE + 0.5):
        raise ValueError("expected calibration coordinates must be inside full scale")
    if np.any(np.diff(raw[np.argsort(expected)]) <= 0):
        raise ValueError("calibration transfer must be strictly increasing")
    if isinstance(gain, (bool, np.bool_)) or not isinstance(gain, Integral):
        raise ValueError("gain must be one of the supported integers: 1, 4, 16")
    normalized_gain = int(gain)
    if normalized_gain not in (1, 4, 16):
        raise ValueError("gain must be 1, 4, or 16")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("instance_id must identify the calibrated model/device")
    if any(ord(char) < 32 for char in instance_id):
        raise ValueError("instance_id must not contain control characters")
    vdd = _finite_scalar(vdd_v, "vdd_v")
    temp = _finite_scalar(temperature_c, "temperature_c")
    if vdd != 1.8 or temp != 27.0:
        raise ValueError("calibration is allowed only at 1.8 V and 27 degrees C")
    return raw, expected, normalized_gain


def fit_calibration(
    raw_means: object,
    expected_codes: object,
    gain: int,
    instance_id: str,
    vdd_v: float = 1.8,
    temperature_c: float = 27.0,
) -> dict:
    """Fit external affine correction, preserving code-center coordinates.

    Use averaged acquisitions at -80%, 0, +80% differential full scale. For
    offset-binary codes the expected coordinate is (vin + FS/2)/LSB - 0.5,
    not the transition index. Acquisition code must additionally check individual
    samples for clipping: an average alone cannot rule out partial saturation.
    Validation/test points must be independent of these fit points.
    """
    raw, expected, normalized_gain = _calibration_inputs(
        raw_means, expected_codes, gain, instance_id, vdd_v, temperature_c
    )
    centered_raw = raw - np.mean(raw)
    centered_expected = expected - np.mean(expected)
    denominator = float(np.dot(centered_raw, centered_raw))
    if denominator <= np.finfo(float).eps**2 * float(np.max(np.abs(raw))) ** 2:
        raise ValueError("calibration raw-code span is numerically degenerate")
    slope = float(np.dot(centered_raw, centered_expected) / denominator)
    intercept = float(np.mean(expected) - slope * np.mean(raw))
    if not math.isfinite(slope) or slope <= 0 or not math.isfinite(intercept):
        raise ValueError("calibration fit is not a finite positive transfer")
    residual = slope * raw + intercept - expected
    return {
        "schema": _CALIBRATION_SCHEMA,
        "method": "external_affine_least_squares",
        "code_convention": "offset_binary_code_center",
        "bits": _BITS,
        "gain": normalized_gain,
        "instance_id": instance_id,
        "vdd_v": 1.8,
        "temperature_c": 27.0,
        "slope": slope,
        "intercept": intercept,
        "raw_means": raw.tolist(),
        "expected_codes": expected.tolist(),
        "fit_max_abs_residual_lsb": float(np.max(np.abs(residual))),
        "fit_rms_residual_lsb": float(np.sqrt(np.mean(residual**2))),
        "clipping": "none",
        "rounding": "none",
    }


def _validate_calibration(calibration: object) -> dict:
    if not isinstance(calibration, dict):
        raise ValueError("calibration must be a coefficient/provenance dictionary")
    fixed = {
        "schema": _CALIBRATION_SCHEMA,
        "method": "external_affine_least_squares",
        "code_convention": "offset_binary_code_center",
        "bits": _BITS,
        "clipping": "none",
        "rounding": "none",
    }
    for key, expected in fixed.items():
        if calibration.get(key) != expected:
            raise ValueError(f"unsupported or missing calibration metadata: {key}")
    required = (
        "raw_means", "expected_codes", "gain", "instance_id", "vdd_v",
        "temperature_c", "slope", "intercept", "fit_max_abs_residual_lsb",
        "fit_rms_residual_lsb",
    )
    if any(key not in calibration for key in required):
        raise ValueError("calibration is missing coefficient or provenance fields")
    recalculated = fit_calibration(
        calibration["raw_means"], calibration["expected_codes"],
        calibration["gain"], calibration["instance_id"],
        calibration["vdd_v"], calibration["temperature_c"],
    )
    for key in ("slope", "intercept", "fit_max_abs_residual_lsb", "fit_rms_residual_lsb"):
        value = _finite_scalar(calibration[key], key)
        if not math.isclose(value, recalculated[key], rel_tol=1e-12, abs_tol=1e-10):
            raise ValueError(f"calibration coefficient/provenance mismatch: {key}")
    return calibration


def apply_calibration(raw_codes: object, calibration: dict) -> np.ndarray:
    """Apply frozen coefficients without clipping, rounding, or refitting.

    The caller must select the coefficient record for the correct instance and
    gain; this function receives no live-device identity to compare against it.
    Output values outside the raw-code range are deliberately retained.
    """
    valid = _validate_calibration(calibration)
    raw = _vector(raw_codes, "raw_codes")
    if np.any(raw < 0) or np.any(raw > _MAX_CODE):
        raise ValueError("raw codes must lie between 0 and 4095")
    corrected = raw * valid["slope"] + valid["intercept"]
    if not np.all(np.isfinite(corrected)):
        raise ValueError("calibration produced nonfinite coordinates")
    return corrected


def endpoint_linearity(transitions_v: object, lsb_v: float) -> dict:
    """Characterize explicit ADC transition voltages, not a code histogram.

    An N-bit monotonic ADC has 2**N-1 internal boundaries: boundary k (1-based)
    separates codes k-1 and k. Adjacent boundaries define finite widths for codes
    1 through 2**N-2. Coincident boundaries indicate a zero-width missing interior
    code; reversed boundaries are invalid rather than silently sorted.

    Endpoint-normalized LSB = (last-first)/(boundary_count-1). Endpoint INL
    subtracts the line through the FIRST AND LAST INTERNAL TRANSITIONS, removing
    gain and offset. Endpoint DNL uses that normalized LSB; nominal DNL instead
    uses the supplied design LSB and retains uniform gain/width error.

    Saturating codes 0 and 2**N-1 have no finite two-boundary width in this input.
    Therefore ``no_missing_codes`` applies only to the listed interior-code range;
    end-code accessibility requires separate input-range/overload validation.
    """
    transitions = _vector(transitions_v, "transitions_v", 3)
    nominal_lsb = _finite_scalar(lsb_v, "lsb_v")
    if nominal_lsb <= 0:
        raise ValueError("lsb_v must be positive")
    count = int(transitions.size)
    code_count = count + 1
    if code_count & (code_count - 1):
        raise ValueError("provide exactly 2**N-1 internal transition boundaries")
    widths = np.diff(transitions)
    if np.any(widths < 0):
        raise ValueError("transition boundaries must be nondecreasing")
    span = float(transitions[-1] - transitions[0])
    if not math.isfinite(span) or span <= 0:
        raise ValueError("transition span must be finite and positive")
    endpoint_lsb = span / (count - 1)
    endpoint_dnl = widths / endpoint_lsb - 1.0
    nominal_dnl = widths / nominal_lsb - 1.0
    ideal_offsets = np.arange(count, dtype=float) * endpoint_lsb
    endpoint_inl = (transitions - transitions[0] - ideal_offsets) / endpoint_lsb
    if not all(np.all(np.isfinite(array)) for array in (endpoint_dnl, nominal_dnl, endpoint_inl)):
        raise ValueError("linearity calculation produced nonfinite values")
    missing = (np.flatnonzero(widths == 0) + 1).tolist()
    return {
        "bits": int(code_count.bit_length() - 1),
        "transition_count": count,
        "nominal_lsb_v": nominal_lsb,
        "endpoint_lsb_v": float(endpoint_lsb),
        "dnl_lsb": endpoint_dnl.tolist(),
        "inl_lsb": endpoint_inl.tolist(),
        "min_dnl_lsb": float(np.min(endpoint_dnl)),
        "max_dnl_lsb": float(np.max(endpoint_dnl)),
        "max_abs_inl_lsb": float(np.max(np.abs(endpoint_inl))),
        "nominal_dnl_lsb": nominal_dnl.tolist(),
        "nominal_min_dnl_lsb": float(np.min(nominal_dnl)),
        "nominal_max_dnl_lsb": float(np.max(nominal_dnl)),
        "dnl_code_indices": list(range(1, code_count - 1)),
        "inl_transition_indices": list(range(1, code_count)),
        "missing_code_indices": missing,
        "no_missing_codes": not missing,
        "missing_code_scope": "interior codes only; end-code accessibility not tested",
        "checked_code_range": [1, code_count - 2],
        "end_codes_tested": False,
    }
