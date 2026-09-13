"""BEHAVIORAL sensor front end and successive-approximation ADC model.

This module is a system-budget aid, not a transistor, Spectre, layout, PDK
Monte Carlo, or silicon model. Capacitor errors are *synthetic sensitivity*
inputs, not a claim about SKY130 matching statistics. Clock jitter, reference
source impedance/droop, comparator regeneration/metastability/kickback, switch
charge injection, common-mode behavior, power, and source-resistor loading and
thermal noise are not modeled. The caller must budget those independently.

Noise parameters describe independent, already sampled RMS voltages: there is
no continuous-time spectrum, source-resistor model, or automatic noise folding.
Settling is a one-pole acquisition approximation initialized to zero and held
between acquisitions, not proof of closed-loop stability or load-drive ability.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Sequence

import numpy as np


def _finite(name: str, value: float, *, nonnegative: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        qualifier = "nonnegative finite" if nonnegative else "finite"
        raise ValueError(f"{name} must be a {qualifier} real number")
    return result


def _integer(name: str, value: int, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} outside supported range")
    return int(value)


def _voltages(input_v: Sequence[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(input_v)
    if np.iscomplexobj(values) or values.dtype.kind not in "biuf":
        raise ValueError("input_v must contain real numeric voltages")
    values = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("input_v must contain only finite voltages")
    return values


def _gain(gain: float) -> float:
    value = _finite("gain", gain)
    if value not in (1, 4, 16):
        raise ValueError("supported gains are 1, 4, and 16")
    return value


@dataclass(frozen=True)
class Spec:
    bits: int = 12
    full_scale_vpp: float = 0.8
    sample_rate_hz: float = 100000.0
    master_clock_hz: float = 1600000.0
    acquisition_cycles: int = 4
    conversion_cycles: int = 12

    def __post_init__(self) -> None:
        # The ideal transfer uses a transition table; bound its allocation.
        _integer("bits", self.bits, 1, 20)
        _integer("acquisition_cycles", self.acquisition_cycles, 1)
        _integer("conversion_cycles", self.conversion_cycles, 1)
        if self.conversion_cycles != self.bits:
            raise ValueError("one synchronous comparison cycle is required per bit")
        for name in ("full_scale_vpp", "sample_rate_hz", "master_clock_hz"):
            if _finite(name, getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.lsb_v <= 0:
            raise ValueError("full_scale_vpp is too small to represent a nonzero LSB")
        expected_clock = self.sample_rate_hz * (
            self.acquisition_cycles + self.conversion_cycles
        )
        if not math.isclose(self.master_clock_hz, expected_clock, rel_tol=1e-12):
            raise ValueError("clock must equal sample rate times total cycles")

    @property
    def lsb_v(self) -> float:
        return self.full_scale_vpp / (1 << self.bits)

    @property
    def acquisition_time_s(self) -> float:
        return self.acquisition_cycles / self.master_clock_hz


@dataclass(frozen=True)
class FrontendParameters:
    dc_gain_db: float = math.inf
    gain_error: float = 0.0
    offset_input_v: float = 0.0
    noise_input_rms_v: float = 0.0
    cubic_per_v2: float = 0.0
    settling_tau_s: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.dc_gain_db, (bool, np.bool_)) or not isinstance(self.dc_gain_db, Real):
            raise ValueError("dc_gain_db must be real, with +inf allowed for ideal gain")
        if self.dc_gain_db != math.inf:
            _finite("dc_gain_db", self.dc_gain_db)
        if _finite("gain_error", self.gain_error) <= -1:
            raise ValueError("gain_error must exceed -1 (positive signal gain)")
        _finite("offset_input_v", self.offset_input_v)
        _finite("noise_input_rms_v", self.noise_input_rms_v, nonnegative=True)
        _finite("cubic_per_v2", self.cubic_per_v2)
        _finite("settling_tau_s", self.settling_tau_s, nonnegative=True)


@dataclass(frozen=True)
class ADCParameters:
    comparator_offset_v: float = 0.0
    comparator_noise_rms_v: float = 0.0
    sampling_noise_rms_v: float = 0.0
    capacitor_relative_errors: Sequence[float] | None = None

    def __post_init__(self) -> None:
        _finite("comparator_offset_v", self.comparator_offset_v)
        _finite("comparator_noise_rms_v", self.comparator_noise_rms_v, nonnegative=True)
        _finite("sampling_noise_rms_v", self.sampling_noise_rms_v, nonnegative=True)
        if self.capacitor_relative_errors is not None:
            errors = _voltages(self.capacitor_relative_errors)
            if errors.ndim != 1 or errors.size < 2 or np.any(errors <= -1):
                raise ValueError("capacitor errors must be a 1-D vector > -1")
            # Keep parameters immutable even if the caller later edits its array.
            object.__setattr__(self, "capacitor_relative_errors", tuple(errors))


def ideal_codes(input_v: Sequence[float] | np.ndarray, spec: Spec) -> np.ndarray:
    """Offset-binary quantization, with equality assigned to the upper code.

Transition k is exactly ``-full_scale_vpp/2 + k*lsb_v`` for k=1..2**N-1.
Out-of-range finite inputs clip to the endpoint codes. A transition table
avoids floor-roundoff incorrectly promoting a nextafter-below-threshold value.
The returned int64 array has the same shape as the input, including scalars.
"""
    values = _voltages(input_v)
    transitions = (
        np.arange(1, 1 << spec.bits, dtype=np.float64) * spec.lsb_v
        - spec.full_scale_vpp / 2
    )
    return np.asarray(np.searchsorted(transitions, values, side="right"), dtype=np.int64)


def _capacitor_weights(spec: Spec, params: ADCParameters) -> tuple[np.ndarray, float]:
    # MSB..LSB plus one dummy unit: ideal total is 2**bits units per side.
    weights = np.append(2.0 ** np.arange(spec.bits - 1, -1, -1), 1.0)
    if params.capacitor_relative_errors is not None:
        errors = np.asarray(params.capacitor_relative_errors, dtype=np.float64)
        if errors.shape != (spec.bits + 1,):
            raise ValueError("capacitor errors must have bits + 1 entries, including dummy")
        with np.errstate(over="ignore", invalid="ignore"):
            weights *= 1 + errors
    with np.errstate(over="ignore", invalid="ignore"):
        total = float(np.sum(weights))
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0) or not math.isfinite(total):
        raise ValueError("capacitor weights and their total must be positive and finite")
    return weights[:-1], total


def sar_codes(
    input_v: Sequence[float] | np.ndarray,
    spec: Spec,
    params: ADCParameters,
    rng: np.random.Generator,
) -> np.ndarray:
    """Perform one comparator decision per bit, MSB first.

The equivalent differential CDAC threshold is -FS/2 + FS*selected_C/total_C.
``capacitor_relative_errors`` has N+1 entries: binary MSB..LSB capacitors,
then the unit dummy. It is a synthetic equivalent differential-array model;
independent positive/negative arrays and common-mode dynamics are not modeled.
Large radix errors can produce missing codes, not just a linear gain change.

Sampling noise is drawn once per conversion and reused for all N decisions.
Comparator noise is redrawn for every decision. A positive comparator offset
increases code. Exact equality keeps the trial bit (upper-code convention).
"""
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a numpy.random.Generator")
    values = _voltages(input_v)
    weights, total = _capacitor_weights(spec, params)
    sampled = values.copy()
    with np.errstate(over="ignore", invalid="ignore"):
        if params.sampling_noise_rms_v:
            sampled += rng.normal(0, params.sampling_noise_rms_v, size=sampled.shape)
        sampled += params.comparator_offset_v
    if not np.all(np.isfinite(sampled)):
        raise ValueError("sampled voltage overflow")
    codes = np.zeros(sampled.shape, dtype=np.int64)
    selected = np.zeros(sampled.shape, dtype=np.float64)
    for index, weight in enumerate(weights):
        trial = selected + weight
        threshold = -spec.full_scale_vpp / 2 + spec.full_scale_vpp * (trial / total)
        comparator_input = sampled
        if params.comparator_noise_rms_v:
            with np.errstate(over="ignore", invalid="ignore"):
                comparator_input = sampled + rng.normal(
                    0, params.comparator_noise_rms_v, size=sampled.shape
                )
            if not np.all(np.isfinite(comparator_input)):
                raise ValueError("comparator input overflow")
        keep = comparator_input >= threshold
        selected = np.where(keep, trial, selected)
        codes |= keep.astype(np.int64) << (spec.bits - 1 - index)
    return codes


def run_chain(
    input_v: Sequence[float] | np.ndarray,
    gain: float,
    spec: Spec,
    frontend: FrontendParameters,
    adc: ADCParameters,
    seed: int = 0,
) -> dict[str, np.ndarray]:
    """Run input-referred errors, a behavioral front end, and the SAR decisions.

Linear gain is G/(1+G/A) * (1+gain_error), A=10**(dc_gain_db/20).
The simplified feedback factor assumes noise gain equals signal gain. This
must be replaced by the actual feedback topology for circuit-level budgeting.
Input offset/noise are applied before gain; cubic error is output-referred:
``v += cubic_per_v2 * v**3``. No amplifier rail clipping is modeled.

Each output sample settles toward its target for acquisition_time_s, starting
from the previous held output (initially zero). This exposes intersample memory
but not continuous-time overload recovery. ADC clipping remains explicit.
"""
    values = _voltages(input_v)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("run_chain input must be a nonempty 1-D voltage sequence")
    nominal_gain = _gain(gain)
    _integer("seed", seed, 0)
    rng = np.random.default_rng(seed)
    if frontend.dc_gain_db == math.inf:
        closed_loop_gain = nominal_gain
    else:
        log_ratio = math.log(nominal_gain) - frontend.dc_gain_db * math.log(10) / 20
        closed_loop_gain = nominal_gain * math.exp(-float(np.logaddexp(0, log_ratio)))
    noisy_input = values + frontend.offset_input_v
    if frontend.noise_input_rms_v:
        noisy_input = noisy_input + rng.normal(
            0, frontend.noise_input_rms_v, size=values.shape
        )
    with np.errstate(over="ignore", invalid="ignore"):
        target = noisy_input * closed_loop_gain * (1 + frontend.gain_error)
        if frontend.cubic_per_v2:
            target = target + frontend.cubic_per_v2 * target**3
    if not np.all(np.isfinite(target)):
        raise ValueError("front-end output overflow")
    output = target.copy()
    if frontend.settling_tau_s:
        # expm1 preserves the update when the acquisition/tau ratio is tiny.
        alpha = -math.expm1(-spec.acquisition_time_s / frontend.settling_tau_s)
        previous = 0.0
        for index, desired in enumerate(target):
            previous += alpha * (desired - previous)
            output[index] = previous
    return {
        "sensor_input_v": values.copy(),
        "frontend_output_v": output,
        "raw_codes": sar_codes(output, spec, adc, rng),
    }


def coherent_tone(
    spec: Spec,
    n_samples: int,
    target_hz: float,
    amplitude_dbfs: float = -1,
    gain: float = 1,
) -> tuple[np.ndarray, float, int]:
    """Generate a coherent sine at the nearest coprime FFT bin below Nyquist.

Input amplitude is FS/2 * 10**(dBFS/20) / gain; dBFS refers to ADC full scale.
No DC or Nyquist bin is chosen. Non-power-of-two record lengths are supported.
The reported actual frequency, rather than target_hz, belongs in result files.
"""
    count = _integer("n_samples", n_samples, 4)
    target = _finite("target_hz", target_hz)
    if not 0 < target < spec.sample_rate_hz / 2:
        raise ValueError("target_hz must be strictly between DC and Nyquist")
    amplitude = _finite("amplitude_dbfs", amplitude_dbfs)
    if amplitude > 0:
        raise ValueError("amplitude_dbfs must not exceed full scale (0 dBFS)")
    nominal_gain = _gain(gain)
    target_bin = target * count / spec.sample_rate_hz
    candidates = (k for k in range(1, (count + 1) // 2) if math.gcd(k, count) == 1)
    fft_bin = min(candidates, key=lambda k: (abs(k - target_bin), k))
    actual_hz = fft_bin * spec.sample_rate_hz / count
    peak = spec.full_scale_vpp / 2 * 10 ** (amplitude / 20) / nominal_gain
    signal = peak * np.sin(2 * np.pi * fft_bin * np.arange(count) / count)
    return signal, actual_hz, fft_bin
