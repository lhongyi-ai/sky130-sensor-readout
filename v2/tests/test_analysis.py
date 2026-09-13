"""Manufactured numerical cases, not evidence of physical ADC performance."""

import copy
import json
import math
import unittest

import numpy as np

from sensor_readout.analysis import (
    apply_calibration,
    endpoint_linearity,
    fit_calibration,
    spectrum_metrics,
)


class SpectrumMetricsTests(unittest.TestCase):
    def setUp(self):
        self.size = 4096
        self.bin = 37
        self.time = np.arange(self.size)
        self.harmonics = {2: 0.020, 3: 0.010, 4: 0.006, 5: 0.004}
        self.noise_amplitude = 0.003

    def manufactured_record(self, fundamental=None):
        fundamental = self.bin if fundamental is None else fundamental
        phase = 2 * np.pi * fundamental * self.time / self.size
        values = np.sin(phase)
        for harmonic, amplitude in self.harmonics.items():
            values += amplitude * np.sin(harmonic * phase + 0.3)
        values += self.noise_amplitude * np.cos(2 * np.pi * 601 * self.time / self.size)
        return values

    def test_known_powers_sndr_snr_thd_and_sfdr(self):
        result = spectrum_metrics(self.manufactured_record(), 100000, self.bin)
        distortion = sum(amplitude**2 for amplitude in self.harmonics.values())
        noise = self.noise_amplitude**2
        self.assertAlmostEqual(result["sndr_db"], -10 * math.log10(distortion + noise), places=10)
        self.assertAlmostEqual(result["snr_db"], -10 * math.log10(noise), places=10)
        self.assertAlmostEqual(result["thd_db"], 10 * math.log10(distortion), places=10)
        self.assertAlmostEqual(result["sfdr_db"], -20 * math.log10(0.020), places=10)
        self.assertAlmostEqual(result["enob"], (result["sndr_db"] - 1.76) / 6.02)
        json.dumps(result, allow_nan=False)

    def test_dc_offset_and_scale_do_not_change_ratios(self):
        baseline = spectrum_metrics(self.manufactured_record(), 100000, self.bin)
        shifted = spectrum_metrics(self.manufactured_record() * 0.003 + 0.9, 100000, self.bin)
        for metric in ("sndr_db", "snr_db", "thd_db", "sfdr_db"):
            self.assertAlmostEqual(baseline[metric], shifted[metric], places=9)

    def test_alias_harmonics_including_above_nyquist(self):
        result = spectrum_metrics(self.manufactured_record(900), 100000, 900)
        self.assertEqual(result["harmonic_alias_bins"], {"2": 1800, "3": 1396, "4": 496, "5": 404})
        distortion = sum(amplitude**2 for amplitude in self.harmonics.values())
        self.assertAlmostEqual(result["thd_db"], 10 * math.log10(distortion), places=10)

    def test_nyquist_weight_and_aliased_harmonic_deduplication(self):
        size = 1024
        index = np.arange(size)
        values = np.cos(2 * np.pi * 256 * index / size)
        values += 0.02 * (-1.0)**index
        values += 0.003 * np.cos(2 * np.pi * 17 * index / size)
        result = spectrum_metrics(values, 100000, 256)
        self.assertEqual(result["counted_harmonic_bins"], [512])
        self.assertEqual(result["unresolvable_harmonic_orders"], [3, 4, 5])
        self.assertAlmostEqual(result["thd_db"], 10 * math.log10(0.02**2 / 0.5), places=10)
        self.assertAlmostEqual(result["sndr_db"], 10 * math.log10(0.5 / (0.02**2 + 0.003**2 / 2)), places=10)

    def test_odd_length_has_no_nyquist_half_weight(self):
        size = 1023
        index = np.arange(size)
        values = np.cos(2 * np.pi * 19 * index / size)
        values += 0.01 * np.cos(2 * np.pi * 38 * index / size)
        values += 0.003 * np.cos(2 * np.pi * 511 * index / size)
        result = spectrum_metrics(values, 100000, 19)
        self.assertAlmostEqual(result["sndr_db"], -10 * math.log10(0.01**2 + 0.003**2), places=10)

    def test_harmonics_are_not_removed_from_sndr(self):
        result = spectrum_metrics(self.manufactured_record(), 100000, self.bin)
        self.assertLess(result["sndr_db"], result["snr_db"] - 10)

    def test_single_harmonic_preserves_sndr_when_noise_is_absent(self):
        phase = 2 * np.pi * self.bin * self.time / self.size
        values = np.sin(phase) + 0.01 * np.sin(2 * phase)
        result = spectrum_metrics(values, 100000, self.bin)
        self.assertAlmostEqual(result["sndr_db"], 40.0, places=10)
        self.assertAlmostEqual(result["sfdr_db"], 40.0, places=10)
        self.assertAlmostEqual(result["thd_db"], -40.0, places=10)
        self.assertIsNone(result["snr_db"])
        self.assertEqual(set(result["metric_unavailable_reasons"]), {"snr_db"})
        json.dumps(result, allow_nan=False)

    def test_nonharmonic_spur_preserves_sndr_when_harmonics_are_absent(self):
        phase = 2 * np.pi * self.bin * self.time / self.size
        values = np.sin(phase) + 0.01 * np.cos(2 * np.pi * 601 * self.time / self.size)
        result = spectrum_metrics(values, 100000, self.bin)
        self.assertAlmostEqual(result["sndr_db"], 40.0, places=10)
        self.assertAlmostEqual(result["sfdr_db"], 40.0, places=10)
        self.assertAlmostEqual(result["snr_db"], 40.0, places=10)
        self.assertIsNone(result["thd_db"])
        self.assertEqual(set(result["metric_unavailable_reasons"]), {"thd_db"})
        json.dumps(result, allow_nan=False)

    def test_sfdr_includes_nonharmonic_spurs(self):
        self.noise_amplitude = 0.025
        result = spectrum_metrics(self.manufactured_record(), 100000, self.bin)
        self.assertAlmostEqual(result["sfdr_db"], -20 * math.log10(0.025), places=10)

    def test_broadband_noise_matches_independent_time_domain_power(self):
        noise = np.random.default_rng(90210).normal(0, 0.001, self.size)
        noise -= np.mean(noise)
        # Remove projections onto the five tones to obtain an exactly known
        # independent noise-power reference, measured in the time domain.
        for order in range(1, 6):
            phase = 2 * np.pi * self.bin * order * self.time / self.size
            for basis in (np.sin(phase), np.cos(phase)):
                noise -= 2 * np.dot(noise, basis) / self.size * basis
        noise_power = float(np.mean(noise**2))
        phase = 2 * np.pi * self.bin * self.time / self.size
        values = np.sin(phase) + 0.01 * np.sin(2 * phase) + noise
        result = spectrum_metrics(values, 100000, self.bin)
        self.assertAlmostEqual(result["snr_db"], 10 * math.log10(0.5 / noise_power), places=9)
        self.assertAlmostEqual(result["sndr_db"], 10 * math.log10(0.5 / (noise_power + 0.01**2 / 2)), places=9)

    def test_invalid_and_degenerate_records_rejected(self):
        valid = self.manufactured_record()
        for values, rate, bin_index in (
            (np.ones(256), 100000, 3),
            (np.zeros(256), 100000, 3),
            ([1, 2, float("nan"), 4, 5, 6, 7, 8], 100000, 1),
            (valid.astype(complex), 100000, 37),
            (valid.reshape(2, -1), 100000, 37),
            (valid, 0, 37),
            (valid, float("inf"), 37),
            (valid, 100000, 0),
            (valid, 100000, self.size // 2),
            (valid, 100000, 37.0),
            (valid, 100000, True),
            (np.sin(2 * np.pi * np.arange(128) / 128), 100000, 1),
        ):
            with self.subTest(rate=rate, bin=bin_index), self.assertRaises(ValueError):
                spectrum_metrics(values, rate, bin_index)


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.expected = np.array([409.1, 2047.5, 3685.9])
        self.slope = 1.02
        self.intercept = -40.85
        self.raw_means = (self.expected - self.intercept) / self.slope
        self.calibration = fit_calibration(self.raw_means, self.expected, 4, "synthetic-case-0")

    def test_affine_fit_independent_holdout(self):
        holdout_expected = np.array([800.3, 1700.1, 2390.2, 3210.4])
        holdout_raw = (holdout_expected - self.intercept) / self.slope
        corrected = apply_calibration(holdout_raw, self.calibration)
        np.testing.assert_allclose(corrected, holdout_expected, atol=1e-10)
        self.assertAlmostEqual(self.calibration["slope"], self.slope)
        self.assertAlmostEqual(self.calibration["intercept"], self.intercept)
        json.dumps(self.calibration, allow_nan=False)

    def test_frozen_calibration_does_not_hide_later_drift(self):
        holdout = np.array([1000.0, 2500.0])
        changed_raw = (holdout - self.intercept) / self.slope + 10
        corrected = apply_calibration(changed_raw, self.calibration)
        np.testing.assert_allclose(corrected - holdout, self.slope * 10, atol=1e-10)
        self.assertEqual(self.calibration["temperature_c"], 27.0)

    def test_no_hidden_clipping_rounding_or_half_lsb_shift(self):
        result = apply_calibration([0, 2047.5, 4095], self.calibration)
        self.assertLess(result[0], 0)
        self.assertGreater(result[-1], 4095)
        self.assertEqual(result.dtype.kind, "f")
        np.testing.assert_allclose(result, np.array([0, 2047.5, 4095]) * self.slope + self.intercept)

    def test_nominal_only_and_valid_provenance(self):
        for overrides in (
            {"vdd_v": 1.62}, {"temperature_c": 85}, {"gain": 2},
            {"gain": True}, {"instance_id": ""}, {"instance_id": "bad\nname"},
        ):
            parameters = {"gain": 4, "instance_id": "synthetic-case-0"}
            parameters.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                fit_calibration(self.raw_means, self.expected, **parameters)

    def test_degenerate_clipped_and_nonmonotonic_fit_rejected(self):
        for raw, expected in (
            ([0, 2000, 4000], self.expected),
            ([20, 2000, 4095], self.expected),
            ([100, 100, 300], self.expected),
            ([100, 200, 300], [400, 400, 600]),
            ([3000, 2000, 1000], self.expected),
            ([100, 200], [100, 200]),
            ([100, 200, float("nan")], self.expected),
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                fit_calibration(raw, expected, 1, "synthetic-bad")

    def test_corrupted_metadata_and_coefficients_rejected(self):
        for key, value in (
            ("slope", 0.1), ("intercept", float("nan")), ("schema", "unknown"),
            ("vdd_v", 1.98), ("instance_id", ""), ("gain", 2),
            ("clipping", "enabled"), ("rounding", "nearest"),
            ("code_convention", "transition_index"),
        ):
            damaged = copy.deepcopy(self.calibration)
            damaged[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                apply_calibration([100, 200], damaged)
        damaged = copy.deepcopy(self.calibration)
        del damaged["raw_means"]
        with self.assertRaises(ValueError):
            apply_calibration([100, 200], damaged)

    def test_bad_raw_codes_rejected_and_serialization_round_trip(self):
        restored = json.loads(json.dumps(self.calibration, allow_nan=False))
        np.testing.assert_allclose(apply_calibration(self.raw_means, restored), self.expected)
        for raw in ([-1, 200], [4096], [float("inf")], [], [[100, 200]]):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                apply_calibration(raw, restored)


class EndpointLinearityTests(unittest.TestCase):
    def test_ideal_twelve_bit_transfer_and_scope(self):
        lsb = 0.8 / 4096
        transitions = -0.4 + np.arange(1, 4096) * lsb
        result = endpoint_linearity(transitions, lsb)
        self.assertEqual(result["transition_count"], 4095)
        self.assertEqual(len(result["dnl_lsb"]), 4094)
        self.assertEqual(len(result["inl_lsb"]), 4095)
        self.assertLess(result["max_abs_inl_lsb"], 1e-9)
        np.testing.assert_allclose(result["dnl_lsb"], 0, atol=1e-9)
        self.assertTrue(result["no_missing_codes"])
        self.assertFalse(result["end_codes_tested"])
        self.assertEqual(result["checked_code_range"], [1, 4094])
        json.dumps(result, allow_nan=False)

    def test_endpoint_removes_gain_offset_but_nominal_dnl_retains_gain(self):
        transitions = np.arange(1, 16) * 1.1 + 20
        result = endpoint_linearity(transitions, 1.0)
        np.testing.assert_allclose(result["dnl_lsb"], 0, atol=1e-13)
        np.testing.assert_allclose(result["inl_lsb"], 0, atol=1e-13)
        np.testing.assert_allclose(result["nominal_dnl_lsb"], 0.1, atol=1e-13)
        self.assertAlmostEqual(result["endpoint_lsb_v"], 1.1)

    def test_known_nonlinearity(self):
        transitions = np.arange(1, 16, dtype=float)
        transitions[7] += 0.25
        result = endpoint_linearity(transitions, 1.0)
        self.assertAlmostEqual(result["max_abs_inl_lsb"], 0.25)
        self.assertAlmostEqual(result["min_dnl_lsb"], -0.25)
        self.assertAlmostEqual(result["max_dnl_lsb"], 0.25)
        self.assertEqual(result["inl_lsb"][0], 0)
        self.assertEqual(result["inl_lsb"][-1], 0)

    def test_zero_width_missing_code_is_not_hidden(self):
        transitions = np.arange(1, 16, dtype=float)
        transitions[7] = transitions[6]
        result = endpoint_linearity(transitions, 1.0)
        self.assertFalse(result["no_missing_codes"])
        self.assertEqual(result["missing_code_indices"], [7])
        self.assertEqual(result["min_dnl_lsb"], -1)

    def test_invalid_boundaries_are_not_sorted_or_assumed_complete(self):
        for transitions, lsb in (
            ([1, 2, 3, 4], 1),
            ([1, 3, 2], 1),
            ([1, 1, 1], 1),
            ([1, 2, float("nan")], 1),
            ([1, 2, 3], 0),
            ([1, 2, 3], float("inf")),
        ):
            with self.subTest(transitions=transitions), self.assertRaises(ValueError):
                endpoint_linearity(transitions, lsb)


if __name__ == "__main__":
    unittest.main()
