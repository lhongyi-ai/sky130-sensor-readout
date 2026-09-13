"""Analytical allocations; none of these numbers constitutes circuit evidence."""

from __future__ import annotations

import math


def calculate_budget(config: dict) -> dict:
    s = config["spec"]
    a = config["analysis"]
    limits = config["qualification"]
    assumptions = config["budget_assumptions"]
    scenario = config["illustrative_budget_scenario"]
    bits, fs = s["bits"], s["full_scale_vpp"]
    levels = 2**bits
    lsb = fs / levels
    acquisition = s["acquisition_cycles"] / s["master_clock_hz"]
    signal_rms = fs / (2 * math.sqrt(2)) * 10 ** (a["amplitude_dbfs"] / 20)
    total_error_rms = signal_rms / 10 ** (limits["nominal_sndr_db"] / 20)
    settling_limit = limits["settling_error_lsb"] * lsb
    max_tau = acquisition / math.log(fs / settling_limit)
    k_b = 1.380649e-23
    kelvin = assumptions["noise_temperature_c"] + 273.15
    c_unit = assumptions["unit_capacitor_candidate_f"]
    c_side = levels * c_unit
    # Two independent equal sampled capacitors: differential variance 2 kT/C.
    differential_ktc_rms = math.sqrt(2 * k_b * kelvin / c_side)
    c_min = 2 * k_b * kelvin / assumptions["sampled_noise_allocation_v_rms"] ** 2
    adc = scenario["adc"]
    fe = scenario["frontend"]
    rows = []
    for gain in config["gains"]:
        rms_terms = {
            "frontend_output_noise_v_rms": gain * fe["noise_input_rms_v"],
            "sampling_noise_v_rms": adc["sampling_noise_rms_v"],
            "comparator_noise_v_rms": adc["comparator_noise_rms_v"],
            "quantization_noise_v_rms": lsb / math.sqrt(12),
            "unmodeled_reserve_v_rms": assumptions["unmodeled_rms_reserve_v"],
        }
        total = math.sqrt(sum(x * x for x in rms_terms.values()))
        # This is a heuristic budget: per-decision comparator noise is not an
        # exact output-code Gaussian. The behavioral simulation checks it too.
        rows.append({
            "gain": gain,
            "sensor_input_full_scale_vpp": fs / gain,
            "sensor_input_lsb_v": lsb / gain,
            **rms_terms,
            "rss_total_v_rms": total,
            "heuristic_sndr_db": 20 * math.log10(signal_rms / total),
            "rms_margin_v": total_error_rms - total,
            "allocation_fits": total <= total_error_rms,
        })
    return {
        "evidence_level": "ANALYTICAL_BUDGET_ONLY",
        "lsb_v": lsb,
        "half_lsb_v": lsb / 2,
        "settling_error_limit_v": settling_limit,
        "acquisition_time_s": acquisition,
        "conversion_time_s": s["conversion_cycles"] / s["master_clock_hz"],
        "frame_time_s": (s["acquisition_cycles"] + s["conversion_cycles"]) / s["master_clock_hz"],
        "input_signal_rms_v": signal_rms,
        "total_error_allowance_v_rms_for_nominal_sndr": total_error_rms,
        "max_single_pole_tau_s_for_full_scale_step": max_tau,
        "candidate_cdac_unit_cap_f": c_unit,
        "candidate_cdac_total_per_side_f": c_side,
        "candidate_differential_ktc_v_rms": differential_ktc_rms,
        "minimum_cap_per_side_from_ktc_only_f": c_min,
        "gains": rows,
        "limitations": [
            "kT/C omits matching, parasitics, switch topology and comparator effects.",
            "One-pole settling is not a stability or transistor bandwidth proof.",
            "Unit capacitor realizability and matching require actual PDK evidence.",
            "RSS treats comparator noise approximately and is not an ENOB prediction.",
            "Power and area cannot be inferred from this model.",
        ],
    }
