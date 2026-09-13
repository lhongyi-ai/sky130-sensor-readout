"""Topology-aware analytical checks, never substitutes for transistor noise.

The continuous-time model is one real pole. Sampling aliases all its noise;
integrating only 0..5 kHz before sampling is not a valid full-Nyquist SNDR
calculation. The assumed pole is not claimed to fit the current circuit.
"""
from __future__ import annotations
import math
import numpy as np

K_B = 1.380649e-23


def _positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")


def resistor_output_psd(gain, input_network_ohm, temperature_c=27):
    """Two independent legs of inverting resistor feedback, V²/Hz.

input_network_ohm includes the real external source resistor. RF=G*RIN.
Each leg contributes 4kT*(RF²/RIN + RF), referred to the amplifier output.
Assumes ideal noiseless amplifier and equal filtering of both contributions.
"""
    _positive(gain, "gain")
    _positive(input_network_ohm, "input network resistance")
    kelvin = temperature_c + 273.15
    _positive(kelvin, "temperature in kelvin")
    rf = gain * input_network_ohm
    return 8 * K_B * kelvin * (rf * rf / input_network_ohm + rf)


def sampled_one_pole_psd(frequency_hz, white_psd_v2_hz, pole_hz, sample_rate_hz):
    """One-sided aliased PSD on [0, fs/2], closed-form infinite alias sum.

Sum over k of S0 / (1+((f+k*fs)/fc)^2). Stable exponential form avoids
overflow of sinh/cosh; integration to fs/2 gives S0*pi*fc/2 exactly.
Endpoint conventions do not affect the integral.
"""
    _positive(pole_hz, "pole")
    _positive(sample_rate_hz, "sample rate")
    if not math.isfinite(white_psd_v2_hz) or white_psd_v2_hz < 0:
        raise ValueError("PSD must be nonnegative and finite")
    frequency = np.asarray(frequency_hz, dtype=float)
    if np.any(~np.isfinite(frequency)) or np.any((frequency < 0) | (frequency > sample_rate_hz / 2)):
        raise ValueError("frequency must be within the first Nyquist band")
    a = 2 * math.pi * pole_hz / sample_rate_hz
    z = math.exp(-a)
    numerator = -math.expm1(-2 * a)
    # (1-z)^2 + 4*z*sin(theta/2)^2 is accurate for very low poles/f.
    denominator = (-math.expm1(-a))**2 + 4 * z * np.sin(math.pi * frequency / sample_rate_hz)**2
    return white_psd_v2_hz * math.pi * pole_hz / sample_rate_hz * numerator / denominator


def one_pole_noise(white_psd_v2_hz, pole_hz, sample_rate_hz, signal_bandwidth_hz=5000):
    _positive(signal_bandwidth_hz, "signal bandwidth")
    if signal_bandwidth_hz > sample_rate_hz / 2:
        raise ValueError("signal bandwidth exceeds Nyquist")
    f = np.linspace(0, signal_bandwidth_hz, 16385)
    folded = float(np.trapezoid(sampled_one_pole_psd(f, white_psd_v2_hz, pole_hz, sample_rate_hz), f))
    unaliased = white_psd_v2_hz * pole_hz * math.atan(signal_bandwidth_hz / pole_hz)
    total = white_psd_v2_hz * math.pi * pole_hz / 2
    return {"full_nyquist_sampled_rms_v": math.sqrt(total),
            "signal_band_sampled_rms_v": math.sqrt(folded),
            "signal_band_before_aliasing_rms_v": math.sqrt(unaliased),
            "signal_band_variance_alias_multiplier": folded / unaliased if unaliased else None}


def make_physical_budget():
    fs, span, bits, acquisition = 100000.0, 0.8, 12, 2.5e-6
    lsb = span / 2**bits
    error = 0.25 * lsb
    tau_max = acquisition / math.log(span / error)
    pole_min = 1 / (2 * math.pi * tau_max)
    signal_rms = span / (2 * math.sqrt(2)) * 10**(-1/20)
    allowed_rms = signal_rms / 10**(65/20)
    unit_c = 2e-15 * (3 + 0.15)**2  # Verified combined-deck nominal formula.
    c_side = 4096 * unit_c
    rows = []
    for total_r in (350.0, 1000.0, 10000.0):
        for gain in (1, 4, 16):
            psd = resistor_output_psd(gain, total_r)
            noise = one_pole_noise(psd, pole_min, fs)
            rows.append({"gain": gain, "source_resistance_per_leg_ohm": 350.0,
                "input_resistor_per_leg_ohm": total_r - 350.0,
                "feedback_resistor_per_leg_ohm": gain * total_r,
                "signal_gain": gain, "noise_gain": 1 + gain,
                "assumed_closed_loop_pole_hz": pole_min,
                "resistor_output_density_v_sqrt_hz": math.sqrt(psd), **noise,
                "resistor_noise_alone_fits_total_sndr_allowance": noise["full_nyquist_sampled_rms_v"] < allowed_rms,
                "resistor_noise_only_snr_upper_bound_db": 20 * math.log10(signal_rms / noise["full_nyquist_sampled_rms_v"]),
                "remaining_other_error_rms_v": math.sqrt(max(0, allowed_rms**2 - noise["full_nyquist_sampled_rms_v"]**2))})
    # Conservative aggregate charge bound, not an exact binary switching
    # sequence and not a prediction of actual reference port power.
    ref_step = 0.4
    q_bound = 2 * c_side * ref_step
    return {"evidence_level": "PDK_INFORMED_ANALYTICAL_BOUNDS_NOT_CHIP_RESULTS",
            "lsb_v": lsb, "settling_limit_v": error, "assumed_single_pole_min_hz": pole_min,
            "allowed_total_rms_error_v_for_65db_sndr": allowed_rms,
            "snr_integrates_full_nyquist_not_just_sensor_band": True,
            "resistor_noise_cases": rows,
            "mim": {"drawn_plate_w_um": 3.0, "drawn_plate_l_um": 3.0,
                "combined_model_nominal_unit_f": unit_c, "capacitance_per_side_f": c_side,
                "two_arrays_drawn_plate_area_um2_not_core_area": 8192 * 9.0,
                "ktc_differential_rms_at_85c_v": math.sqrt(2*K_B*(85+273.15)/c_side)},
            "reference_conservative_bounds": {"worst_aggregate_switched_charge_c": q_bound,
                "ideal_current_for_2ns_transition_a": q_bound / 2e-9,
                "local_decoupling_if_entire_charge_supplied_for_0p25lsb_droop_f": q_bound / error,
                "single_pole_r_max_200ns_settle_one_side_ohm": 200e-9 / (c_side * math.log(ref_step / error)),
                "explanation": "Upper bounds; two arrays treated as simultaneously switching all capacitance. Actual reference current, charge recycling, driver resistance, decoupling ESR/ESL and port energy require transient measurements."},
            "limitations": ["The one-pole amplifier is an analytical candidate, not a fit to the current transistor circuit.",
                "A physical sample switch/RC load filters noise differently; transistor integration is still mandatory.",
                "No flicker noise, current noise, CMFB mismatch leakage, comparator noise or distortion is included in resistor-only figures.",
                "350-ohm case needs zero input resistor and is a lower-bound comparison, not a selected realizable PGA.",
                "MIM plate area excludes routing, keepouts, dummies, transistors, resistors and digital implementation.",
                "Full-Nyquist FFT SNDR cannot be replaced by a 0..5kHz-only integration without a specification review."]}
