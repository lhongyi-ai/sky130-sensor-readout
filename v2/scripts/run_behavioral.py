#!/usr/bin/env python3
"""Reproduce M2 behavioral experiments; never qualify a physical chip."""

from __future__ import annotations

import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sensor_readout.analysis import (  # noqa: E402
    apply_calibration, endpoint_linearity, fit_calibration, spectrum_metrics,
)
from sensor_readout.budget import calculate_budget  # noqa: E402
from sensor_readout.model import (  # noqa: E402
    ADCParameters, FrontendParameters, Spec, coherent_tone, run_chain, sar_codes,
)


def save_json(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def save_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_config(config: dict) -> None:
    frozen_spec = {"bits": 12, "full_scale_vpp": 0.8, "sample_rate_hz": 100000.0,
                   "master_clock_hz": 1600000.0, "acquisition_cycles": 4, "conversion_cycles": 12}
    frozen_limits = {
        "nominal_sndr_db": 65.0, "corner_sndr_db": 62.0,
        "nominal_core_power_w": 0.002, "corner_core_power_w": 0.003,
        "settling_error_lsb": 0.25, "nominal_calibration_residual_lsb": 1.0,
        "corner_calibration_residual_lsb": 4.0, "inl_abs_lsb": 1.5,
        "dnl_min_lsb": -0.9, "dnl_max_lsb": 1.5, "phase_margin_deg": 60.0,
        "process_corners": ["TT", "FF", "SS", "FS", "SF"],
        "supply_voltages_v": [1.62, 1.8, 1.98], "temperatures_c": [-20.0, 27.0, 85.0],
        "common_mode_offsets_v": [-0.05, 0.0, 0.05], "source_resistance_per_leg_ohm": 350.0,
        "source_resistance_sensitivity_ohm": [0.0, 1000.0], "mismatch_static_samples_min": 200,
    }
    if config["spec"] != frozen_spec or config["gains"] != [1, 4, 16]:
        raise ValueError("changing the approved resolution/range/timing/gains requires a reviewed spec revision")
    if config["qualification"] != frozen_limits:
        raise ValueError("changing a qualification limit/matrix requires a reviewed spec revision")
    if (config["analysis"]["tone_targets_hz"] != [1000.0, 5000.0]
            or config["analysis"]["adc_tone_target_hz"] != 45000.0
            or config["analysis"]["amplitude_dbfs"] != -1.0):
        raise ValueError("changing qualification tones/amplitude requires a reviewed spec revision")
    if config["analysis"]["calibration_input_fractions"] != [-0.8, 0.0, 0.8]:
        raise ValueError("calibration must use the frozen -80%, 0%, +80% points")
    n = config["analysis"]["fft_samples"]
    if not isinstance(n, int) or n < 16384 or n & (n - 1):
        raise ValueError("FFT record must be a power of two with at least 16384 samples")
    for key in ("calibration_samples_per_point", "holdout_samples_per_point"):
        if not isinstance(config["analysis"][key], int) or config["analysis"][key] < 1:
            raise ValueError(f"{key} must be a positive integer")


def calibrate(config, spec, frontend, adc, gain):
    analysis = config["analysis"]
    raw_means, expected = [], []
    acquisitions = []
    for index, fraction in enumerate(analysis["calibration_input_fractions"]):
        sensor_v = fraction * spec.full_scale_vpp / (2 * gain)
        # Let the one-pole model reach DC before retaining the acquisition.
        n = analysis["calibration_samples_per_point"]
        result = run_chain(np.full(n + 128, sensor_v), gain, spec, frontend, adc,
                           seed=analysis["seed"] + gain * 10 + index)
        raw = result["raw_codes"][128:]
        if np.any((raw == 0) | (raw == 2**spec.bits - 1)):
            raise ValueError("calibration acquisition touches a code rail")
        raw_means.append(float(np.mean(raw)))
        expected.append((sensor_v * gain + spec.full_scale_vpp / 2) / spec.lsb_v - 0.5)
        acquisitions.append({"sensor_input_v": sensor_v, "raw_mean": raw_means[-1],
                             "raw_std_lsb": float(np.std(raw)), "samples": n})
    fitted = fit_calibration(raw_means, expected, gain, "assumed_budget_instance")
    fitted["evidence_level"] = "SYNTHETIC_BEHAVIORAL_CALIBRATION"
    fitted["acquisitions"] = acquisitions
    return fitted


def holdout(config, spec, frontend, adc, gain, calibration):
    rows = []
    n = config["analysis"]["holdout_samples_per_point"]
    calibration_fractions = config["analysis"]["calibration_input_fractions"]
    for index, fraction in enumerate(np.linspace(-0.9, 0.9, 65)):
        if any(np.isclose(fraction, x, rtol=0, atol=1e-12) for x in calibration_fractions):
            continue
        sensor = float(fraction * spec.full_scale_vpp / (2 * gain))
        raw = run_chain(np.full(n + 128, sensor), gain, spec, frontend, adc,
                        seed=config["analysis"]["seed"] + 10000 + gain * 100 + index)["raw_codes"][128:]
        expected = (sensor * gain + spec.full_scale_vpp / 2) / spec.lsb_v - 0.5
        corrected = apply_calibration(raw, calibration)
        rows.append({
            "gain": gain, "sensor_input_v": sensor, "expected_code_center": expected,
            "raw_mean": float(np.mean(raw)), "corrected_mean": float(np.mean(corrected)),
            "raw_error_lsb": float(np.mean(raw) - expected),
            "corrected_error_lsb": float(np.mean(corrected) - expected),
            "corrected_sample_std_lsb": float(np.std(corrected)), "samples_averaged": n,
            "rail_hit": bool(np.any((raw == 0) | (raw == 2**spec.bits - 1))),
        })
    return rows


def deterministic_transitions(spec, adc):
    """Locate every internal transition, including duplicates for missing codes.

    A monotone binary decision tree permits bisection of the predicate code>=k.
    Noise must be zero; saturation-code accessibility is checked separately.
    """
    if adc.comparator_noise_rms_v or adc.sampling_noise_rms_v:
        raise ValueError("transition extraction needs deterministic ADC parameters")
    low = np.full(2**spec.bits - 1, -spec.full_scale_vpp / 2)
    high = np.full_like(low, spec.full_scale_vpp / 2)
    wanted = np.arange(1, 2**spec.bits)
    rng = np.random.default_rng(0)
    for _ in range(48):
        mid = (low + high) / 2
        codes = sar_codes(mid, spec, adc, rng)
        high = np.where(codes >= wanted, mid, high)
        low = np.where(codes < wanted, mid, low)
    return high


def run(output_dir: Path | None = None) -> dict:
    config_path = ROOT / "config/spec.json"
    config = json.loads(config_path.read_text())
    validate_config(config)
    output = ROOT / "results" if output_dir is None else Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    spec = Spec(**config["spec"])
    scenario = config["illustrative_budget_scenario"]
    frontend = FrontendParameters(**scenario["frontend"])
    adc = ADCParameters(**scenario["adc"])
    analysis = config["analysis"]
    limits = config["qualification"]
    n = analysis["fft_samples"]
    calibrations, static_rows, spectral_rows, trace_rows = {}, [], [], []
    static_summary = []

    for gain in config["gains"]:
        calibration = calibrate(config, spec, frontend, adc, gain)
        calibrations[str(gain)] = calibration
        rows = holdout(config, spec, frontend, adc, gain, calibration)
        static_rows.extend(rows)
        residual = max(abs(row["corrected_error_lsb"]) for row in rows)
        static_summary.append({"gain": gain, "holdout_points": len(rows),
                               "raw_max_abs_mean_error_lsb": max(abs(r["raw_error_lsb"]) for r in rows),
                               "corrected_max_abs_mean_error_lsb": residual,
                               "mean_residual_target_met": residual <= limits["nominal_calibration_residual_lsb"],
                               "rail_hits": sum(r["rail_hit"] for r in rows)})
        for target in analysis["tone_targets_hz"]:
            tone, actual_hz, fft_bin = coherent_tone(
                spec, n, target, analysis["amplitude_dbfs"], gain)
            for label, fe, converter in (
                ("ideal_quantized", FrontendParameters(), ADCParameters()),
                ("assumed_budget", frontend, adc),
                ("high_noise_negative_control", replace(frontend, noise_input_rms_v=60e-6),
                 replace(adc, comparator_noise_rms_v=500e-6)),
            ):
                # A complete discarded period prevents startup from polluting FFT.
                result = run_chain(np.tile(tone, 2), gain, spec, fe, converter,
                                   seed=analysis["seed"] + gain + int(target))
                raw = result["raw_codes"][-n:]
                metrics = spectrum_metrics(raw, spec.sample_rate_hz, fft_bin)
                row = {"scenario": label, "gain": gain, "target_hz": target,
                       "actual_hz": actual_hz, "fft_bin": fft_bin, "sample_count": n,
                       "sndr_db": metrics["sndr_db"], "enob_uncorrected_for_input_backoff": metrics["enob"],
                       "sfdr_db": metrics["sfdr_db"], "snr_db": metrics["snr_db"],
                       "thd_db": metrics["thd_db"],
                       "nominal_model_target_met": metrics["sndr_db"] >= limits["nominal_sndr_db"],
                       "evidence_level": "BEHAVIORAL_NOT_TRANSISTOR"}
                if label == "assumed_budget":
                    corrected = apply_calibration(raw, calibration)
                    calibrated_metrics = spectrum_metrics(corrected, spec.sample_rate_hz, fft_bin)
                    if abs(calibrated_metrics["sndr_db"] - metrics["sndr_db"]) > 1e-8:
                        raise AssertionError("affine calibration must not manufacture SNDR improvement")
                    for i in range(n):
                        trace_rows.append({"gain": gain, "target_hz": target, "sample": i,
                                           "sensor_input_v": float(tone[i]),
                                           "frontend_output_v": float(result["frontend_output_v"][-n + i]),
                                           "raw_code": int(raw[i]), "corrected_code_float": float(corrected[i])})
                spectral_rows.append(row)

    adc_rows = []
    tone, actual_hz, fft_bin = coherent_tone(spec, n, analysis["adc_tone_target_hz"],
                                           analysis["amplitude_dbfs"], 1)
    raw = sar_codes(tone, spec, adc, np.random.default_rng(analysis["seed"]))
    adc_rows.append({"evidence_level": "BEHAVIORAL_NOT_TRANSISTOR",
                     "scenario": "standalone_assumed_adc", "actual_hz": actual_hz,
                     **spectrum_metrics(raw, spec.sample_rate_hz, fft_bin)})

    linearity, linearity_rows = {}, []
    bad_caps = [0.0] * (spec.bits + 1)
    bad_caps[0] = 0.004
    for label, converter in (("ideal", ADCParameters()),
                             ("synthetic_radix_error", ADCParameters(capacitor_relative_errors=bad_caps))):
        boundaries = deterministic_transitions(spec, converter)
        data = endpoint_linearity(boundaries, spec.lsb_v)
        endpoint_codes = sar_codes(np.array([-0.4, 0.4]), spec, converter, np.random.default_rng(0))
        accessible = bool(endpoint_codes[0] == 0 and endpoint_codes[1] == 2**spec.bits - 1)
        passed = (data["no_missing_codes"] and accessible
                  and data["max_abs_inl_lsb"] <= limits["inl_abs_lsb"]
                  and data["min_dnl_lsb"] >= limits["dnl_min_lsb"]
                  and data["max_dnl_lsb"] <= limits["dnl_max_lsb"])
        data["endpoint_codes_accessible"] = accessible
        data["linearity_targets_met"] = bool(passed)
        data["evidence_level"] = "SYNTHETIC_DETERMINISTIC_MODEL_NOT_PDK_MISMATCH"
        linearity[label] = data
        linearity_rows.extend({"scenario": label, "transition_to_code": i + 1,
                               "transition_v": float(v)} for i, v in enumerate(boundaries))

    # Explicitly keep a calibration from nominal while injecting unmeasured
    # 100-uV input-offset drift; this is NOT a temperature/PVT model.
    drift_rows = []
    for gain in config["gains"]:
        rows = holdout(config, spec, replace(frontend, offset_input_v=frontend.offset_input_v + 100e-6),
                       adc, gain, calibrations[str(gain)])
        residual = max(abs(r["corrected_error_lsb"]) for r in rows)
        drift_rows.append({"gain": gain, "assumed_input_offset_drift_v": 100e-6,
                           "fixed_calibration_max_abs_mean_residual_lsb": residual,
                           "corner_residual_target_met": residual <= limits["corner_calibration_residual_lsb"],
                           "evidence_level": "SYNTHETIC_DRIFT_NOT_PVT"})

    settling_rows = []
    for label, tau in (("allocated", frontend.settling_tau_s), ("slow_negative_control", 2e-6)):
        step = np.array([-0.4] * 128 + [0.4])
        result = run_chain(step, 1, spec, FrontendParameters(settling_tau_s=tau), ADCParameters())
        error = abs(float(result["frontend_output_v"][-1]) - 0.4)
        settling_rows.append({"scenario": label, "tau_s": tau, "acquisition_time_s": spec.acquisition_time_s,
                              "residual_v": error, "residual_lsb": error / spec.lsb_v,
                              "target_met": error <= limits["settling_error_lsb"] * spec.lsb_v,
                              "evidence_level": "ONE_POLE_MODEL_NOT_LOOP_STABILITY"})

    matrix = [{"corner": corner, "vdd_v": vdd, "temperature_c": temp, "gain": gain,
               "status": "NOT_RUN_REQUIRES_TRANSISTOR_MODEL", "evidence_level": "TEST_DEFINITION_ONLY"}
              for corner in limits["process_corners"] for vdd in limits["supply_voltages_v"]
              for temp in limits["temperatures_c"] for gain in config["gains"]]
    budget = calculate_budget(config)
    assertions = {
        "assumed_nominal_sndr_targets_met": all(r["nominal_model_target_met"] for r in spectral_rows
                                               if r["scenario"] == "assumed_budget"),
        "assumed_nominal_calibration_targets_met": all(r["mean_residual_target_met"] for r in static_summary),
        "allocated_settling_target_met": settling_rows[0]["target_met"],
        "rss_budget_allocations_fit": all(r["allocation_fits"] for r in budget["gains"]),
        "ideal_linearity_passes": linearity["ideal"]["linearity_targets_met"],
        "cdac_negative_control_fails": not linearity["synthetic_radix_error"]["linearity_targets_met"],
        "all_high_noise_controls_fail_sndr": all(not r["nominal_model_target_met"] for r in spectral_rows
                                                 if r["scenario"] == "high_noise_negative_control"),
        "slow_settling_control_fails": not settling_rows[-1]["target_met"],
        "fixed_calibration_exposes_high_gain_drift": not drift_rows[-1]["corner_residual_target_met"],
        "pvt_matrix_not_fabricated": len(matrix) == 135 and all(r["status"].startswith("NOT_RUN") for r in matrix),
        "no_calibration_or_holdout_clipping": all(r["rail_hits"] == 0 for r in static_summary),
    }
    summary = {
        "status": "BEHAVIORAL_EXPERIMENTS_COMPLETE" if all(assertions.values()) else "REGRESSION_FAILURE",
        "evidence_level": "BEHAVIORAL_AND_ANALYTICAL_ONLY",
        "cadence_status": "DEFERRED_BY_USER", "m2_gate": "PARTIAL_PDK_FEASIBILITY_NOT_VERIFIED",
        "physical_chip_qualified": False, "pvt_verified": False, "mismatch_verified": False,
        "assumptions": scenario, "static_calibration": static_summary,
        "standalone_adc_spectrum": adc_rows, "synthetic_offset_drift": drift_rows,
        "settling": settling_rows, "regression_assertions": assertions,
        "spectrum_metadata": {"window": "rectangular_coherent", "noise_in_sndr": True,
                              "harmonics_in_sndr": "all", "thd_harmonics": "2 through 5 with aliases",
                              "enob": "(SNDR-1.76)/6.02, no -1dBFS amplitude correction",
                              "noise_source": "assumed sampled RMS, NOT a physical noise integration"},
        "unverified": ["PDK capacitor realization/matching", "source loading and resistor noise",
                       "noise folding", "reference impedance/droop", "common-mode feedback/stability",
                       "kickback/metastability", "actual PVT/mismatch", "physical digital timing",
                       "power/area", "layout/DRC/LVS/PEX"],
    }
    save_json(output / "behavioral_summary.json", summary)
    save_json(output / "error_budget.json", budget)
    save_json(output / "calibration_coefficients.json", calibrations)
    save_json(output / "linearity.json", linearity)
    save_csv(output / "spectral_metrics.csv", spectral_rows)
    save_csv(output / "calibration_holdout.csv", static_rows)
    save_csv(output / "tone_samples.csv", trace_rows)
    save_csv(output / "adc_transitions.csv", linearity_rows)
    save_csv(output / "qualification_matrix.csv", matrix)
    model_rows = [r for r in spectral_rows if r["scenario"] == "assumed_budget"]
    report = ["# V2 本地行为实验结果", "", "仅为行为模型和预算，不是 SKY130 电路性能。",
              "Cadence 暂停；M2 尚缺 PDK 可行性证据，不能记为完整通过。", "",
              "## 假设预算下的采样结果", "", "| 增益 | 输入频率 Hz | SNDR dB | ENOB |",
              "|---|---:|---:|---:|"]
    report.extend(f"| {r['gain']} | {r['actual_hz']:.3f} | {r['sndr_db']:.3f} | {r['enob_uncorrected_for_input_backoff']:.3f} |"
                  for r in model_rows)
    report += ["", "这些数字依赖配置中的假设噪声/增益/失调参数，不能用于宣称芯片达标。",
               "线性校准改善静态误差，不改变 SNDR；该不变性已自动检查。", "",
               "## 独立静态校准验证", "", "| 增益 | 校准前最大平均误差 LSB | 校准后 |",
               "|---|---:|---:|"]
    report.extend(f"| {r['gain']} | {r['raw_max_abs_mean_error_lsb']:.3f} | {r['corrected_max_abs_mean_error_lsb']:.3f} |"
                  for r in static_summary)
    report += ["", "误差为多次采样后的平均值，不代表单次转换精度。测试点与标定点分离。",
               "", "## 失败保留与证据边界", ""]
    report.extend(f"- {key}: {'PASS' if ok else 'FAIL'}" for key, ok in assertions.items())
    report += ["", "PASS 在此表示检测程序正确识别了预设失败，并非芯片通过验收。",
               "45 个工艺/温压点乘三档增益的 135 行仅为测试定义，全部仍为 NOT_RUN。",
               "", "## 关键预算", "",
               f"- LSB：{budget['lsb_v'] * 1e6:.6f} µV；0.25 LSB：{budget['settling_error_limit_v'] * 1e6:.6f} µV。",
               f"- 采集窗口：{budget['acquisition_time_s'] * 1e6:.3f} µs；满幅阶跃的单极点时间常数上限：{budget['max_single_pole_tau_s_for_full_scale_step'] * 1e9:.3f} ns。",
               f"- 20 fF 单元仅为候选假设，对应每侧 {budget['candidate_cdac_total_per_side_f'] * 1e12:.2f} pF；尚未证明版图实现或匹配。",
               "- 噪声折叠、参考源动态负载、真实比较器、功耗、面积、版图及寄生仍待电路验证。", ""]
    (output / "behavioral_report.md").write_text("\n".join(report))
    sources = [config_path, Path(__file__).resolve(), *sorted((ROOT / "sensor_readout").glob("*.py"))]
    outputs = sorted(p for p in output.iterdir() if p.is_file() and p.name != "behavioral_manifest.json"
                     and p.name in {"behavioral_summary.json", "error_budget.json", "calibration_coefficients.json",
                                    "linearity.json", "spectral_metrics.csv", "calibration_holdout.csv",
                                    "tone_samples.csv", "adc_transitions.csv", "qualification_matrix.csv", "behavioral_report.md"})
    save_json(output / "behavioral_manifest.json", {
        "schema_version": 1, "python": sys.version.split()[0], "numpy": np.__version__,
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "output_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs},
        "seed": analysis["seed"], "evidence_level": "BEHAVIORAL_REPRODUCIBILITY_ONLY",
    })
    if not all(assertions.values()):
        raise AssertionError(f"regression assertions failed: {assertions}")
    return summary


if __name__ == "__main__":
    result = run()
    print(json.dumps({"status": result["status"], "m2_gate": result["m2_gate"],
                      "physical_chip_qualified": False, "results": str(ROOT / "results")}, indent=2))
