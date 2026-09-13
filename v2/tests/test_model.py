"""Independent transfer and error-mechanism tests for the behavioral model."""

import math
import unittest

import numpy as np

from sensor_readout.model import (
    ADCParameters, FrontendParameters, Spec, coherent_tone, ideal_codes,
    run_chain, sar_codes,
)


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.spec = Spec()

    def test_full_code_range_centers(self):
        codes = np.arange(4096)
        centers = -0.4 + (codes + 0.5) * self.spec.lsb_v
        np.testing.assert_array_equal(ideal_codes(centers, self.spec), codes)
        np.testing.assert_array_equal(
            sar_codes(centers, self.spec, ADCParameters(), np.random.default_rng(1)),
            codes,
        )

    def test_every_threshold_and_adjacent_float(self):
        upper = np.arange(1, 4096)
        transitions = -0.4 + upper * self.spec.lsb_v
        for values, expected in (
            (transitions, upper),
            (np.nextafter(transitions, -np.inf), upper - 1),
            (np.nextafter(transitions, np.inf), upper),
        ):
            np.testing.assert_array_equal(ideal_codes(values, self.spec), expected)
            np.testing.assert_array_equal(
                sar_codes(values, self.spec, ADCParameters(), np.random.default_rng(7)),
                expected,
            )

    def test_endpoints_and_scalar(self):
        inputs = [-1e200, -0.4, 0, 0.4, 1e200]
        expected = [0, 0, 2048, 4095, 4095]
        np.testing.assert_array_equal(ideal_codes(inputs, self.spec), expected)
        np.testing.assert_array_equal(
            sar_codes(inputs, self.spec, ADCParameters(), np.random.default_rng(2)),
            expected,
        )
        self.assertEqual(ideal_codes(0.0, self.spec).shape, ())
        self.assertEqual(sar_codes(0.0, self.spec, ADCParameters(), np.random.default_rng()).item(), 2048)

    def test_random_ideal_sar_agreement_and_shape(self):
        inputs = np.random.default_rng(10).uniform(-0.8, 0.8, (300, 200))
        actual = sar_codes(inputs, self.spec, ADCParameters(), np.random.default_rng(20))
        np.testing.assert_array_equal(actual, ideal_codes(inputs, self.spec))
        self.assertEqual(actual.dtype, np.int64)

    def test_zero_capacitor_errors_are_ideal(self):
        inputs = np.linspace(-0.45, 0.45, 20001)
        params = ADCParameters(capacitor_relative_errors=np.zeros(13))
        np.testing.assert_array_equal(
            sar_codes(inputs, self.spec, params, np.random.default_rng(0)),
            ideal_codes(inputs, self.spec),
        )

    def test_capacitor_errors_create_missing_codes(self):
        # Two-bit physical weights [0.8, 1, 1] have an underweight MSB.
        spec = Spec(bits=2, conversion_cycles=2, master_clock_hz=600000)
        errors = np.array([-0.6, 0, 0])
        params = ADCParameters(capacitor_relative_errors=errors)
        errors[:] = 0  # Parameter copying protects against caller mutations.
        codes = sar_codes(np.linspace(-0.4, 0.4, 2001), spec, params, np.random.default_rng(0))
        self.assertTrue(np.all(np.diff(codes) >= 0))
        np.testing.assert_array_equal(np.unique(codes), [0, 2, 3])

    def test_comparator_offset_sign(self):
        offset = 3 * self.spec.lsb_v
        code = sar_codes([self.spec.lsb_v / 2], self.spec,
                         ADCParameters(comparator_offset_v=offset), np.random.default_rng(0))
        self.assertEqual(code[0], 2051)

    def test_sampling_noise_is_drawn_once_per_conversion(self):
        inputs = np.linspace(-0.3, 0.3, 200)
        rms = self.spec.lsb_v * 2
        expected_rng = np.random.default_rng(100)
        expected = ideal_codes(inputs + expected_rng.normal(0, rms, inputs.shape), self.spec)
        actual_rng = np.random.default_rng(100)
        actual = sar_codes(inputs, self.spec, ADCParameters(sampling_noise_rms_v=rms), actual_rng)
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(actual_rng.random(), expected_rng.random())

    def test_comparator_noise_is_drawn_per_decision(self):
        inputs = np.zeros(20)
        actual_rng = np.random.default_rng(123)
        sar_codes(inputs, self.spec, ADCParameters(comparator_noise_rms_v=1e-4), actual_rng)
        expected_rng = np.random.default_rng(123)
        for _ in range(12):
            expected_rng.normal(0, 1e-4, inputs.shape)
        self.assertEqual(actual_rng.random(), expected_rng.random())


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.spec = Spec()
        self.adc = ADCParameters()

    def test_linear_gain_offset_and_finite_loop_gain(self):
        values = np.array([-0.05, 0, 0.05])
        frontend = FrontendParameters(dc_gain_db=60, gain_error=0.02, offset_input_v=0.001)
        actual = run_chain(values, 4, self.spec, frontend, self.adc)
        expected = (values + 0.001) * (4 / (1 + 4 / 1000)) * 1.02
        np.testing.assert_allclose(actual["frontend_output_v"], expected, rtol=1e-14)
        np.testing.assert_array_equal(actual["raw_codes"], ideal_codes(expected, self.spec))
        np.testing.assert_array_equal(actual["sensor_input_v"], values)

    def test_cubic_output_error(self):
        actual = run_chain([0.01, 0.02], 4, self.spec,
                           FrontendParameters(cubic_per_v2=0.2), self.adc)
        nominal = np.array([0.04, 0.08])
        np.testing.assert_allclose(actual["frontend_output_v"], nominal + 0.2 * nominal**3)

    def test_settling_has_history_and_known_time_constant(self):
        tau = self.spec.acquisition_time_s
        actual = run_chain([0.2, 0.2, 0], 1, self.spec,
                           FrontendParameters(settling_tau_s=tau), self.adc)
        decay = math.exp(-1)
        expected = [0.2 * (1 - decay), 0.2 * (1 - decay**2), 0.2 * (1 - decay**2) * decay]
        np.testing.assert_allclose(actual["frontend_output_v"], expected)
        self.assertGreater(actual["frontend_output_v"][-1], 0)

    def test_noisy_seed_reproducibility(self):
        frontend = FrontendParameters(noise_input_rms_v=2e-4)
        adc = ADCParameters(sampling_noise_rms_v=1e-4, comparator_noise_rms_v=5e-5)
        inputs = np.zeros(1000)
        a = run_chain(inputs, 4, self.spec, frontend, adc, seed=31)
        b = run_chain(inputs, 4, self.spec, frontend, adc, seed=31)
        c = run_chain(inputs, 4, self.spec, frontend, adc, seed=32)
        for key in a:
            np.testing.assert_array_equal(a[key], b[key])
        self.assertFalse(np.array_equal(a["raw_codes"], c["raw_codes"]))
        self.assertGreater(np.std(a["frontend_output_v"]), 0)

    def test_extreme_finite_gain_does_not_overflow(self):
        low = run_chain([0.01], 16, self.spec, FrontendParameters(dc_gain_db=-10000), self.adc)
        high = run_chain([0.01], 16, self.spec, FrontendParameters(dc_gain_db=10000), self.adc)
        self.assertEqual(low["frontend_output_v"][0], 0)
        self.assertEqual(high["frontend_output_v"][0], 0.16)


class ToneAndValidationTests(unittest.TestCase):
    def test_spec_properties(self):
        spec = Spec()
        self.assertAlmostEqual(spec.lsb_v, 0.8 / 4096)
        self.assertAlmostEqual(spec.acquisition_time_s, 2.5e-6)

    def test_coherent_tone(self):
        spec = Spec()
        signal, actual, fft_bin = coherent_tone(spec, 16384, 1000, gain=4)
        self.assertEqual(math.gcd(fft_bin, 16384), 1)
        self.assertEqual(actual, fft_bin * 100000 / 16384)
        self.assertLess(abs(actual - 1000), 100000 / 16384)
        self.assertLessEqual(np.max(np.abs(signal)), 0.4 / 4)
        transform = np.abs(np.fft.rfft(signal))
        self.assertEqual(np.argmax(transform), fft_bin)
        transform[fft_bin] = 0
        self.assertLess(np.max(transform), 1e-8)

    def test_near_nyquist_never_selects_alias_or_nyquist(self):
        spec = Spec()
        for count in (4, 5, 30, 16384):
            _, frequency, fft_bin = coherent_tone(spec, count, 49999)
            self.assertLess(frequency, 50000)
            self.assertGreater(frequency, 0)
            self.assertEqual(math.gcd(fft_bin, count), 1)

    def test_invalid_specs(self):
        for kwargs in (
            {"bits": 0}, {"bits": 21}, {"bits": True},
            {"bits": 12.0}, {"conversion_cycles": 11},
            {"acquisition_cycles": 0}, {"sample_rate_hz": 0},
            {"full_scale_vpp": -0.8}, {"master_clock_hz": 1e6},
            {"full_scale_vpp": np.nan}, {"sample_rate_hz": np.inf},
            {"full_scale_vpp": "0.8"}, {"full_scale_vpp": 1e-323},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Spec(**kwargs)

    def test_invalid_error_parameters(self):
        for kwargs in (
            {"dc_gain_db": -np.inf}, {"dc_gain_db": np.nan},
            {"gain_error": -1}, {"noise_input_rms_v": -1},
            {"offset_input_v": np.nan}, {"cubic_per_v2": np.inf},
            {"settling_tau_s": -1},
            {"gain_error": "0.1"}, {"offset_input_v": np.complex128(1 + 2j)},
            {"dc_gain_db": [60]}, {"dc_gain_db": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FrontendParameters(**kwargs)
        for kwargs in (
            {"comparator_noise_rms_v": -1}, {"sampling_noise_rms_v": np.inf},
            {"comparator_offset_v": np.nan}, {"capacitor_relative_errors": [-1, 0]},
            {"capacitor_relative_errors": [[0, 0]]},
            {"capacitor_relative_errors": [np.nan, 0]},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ADCParameters(**kwargs)

    def test_invalid_array_gain_and_cap_shape(self):
        spec = Spec()
        for value in ([np.nan], [np.inf], [1 + 2j], ["0.1"]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ideal_codes(value, spec)
        for gain in (0, 2, 8, np.nan, True):
            with self.subTest(gain=gain), self.assertRaises(ValueError):
                run_chain([0], gain, spec, FrontendParameters(), ADCParameters())
        for values in ([], [[0.1]], 0.1):
            with self.subTest(values=values), self.assertRaises(ValueError):
                run_chain(values, 1, spec, FrontendParameters(), ADCParameters())
        with self.assertRaises(ValueError):
            sar_codes([0], spec, ADCParameters(capacitor_relative_errors=[0, 0]), np.random.default_rng())
        with self.assertRaises(TypeError):
            sar_codes([0], spec, ADCParameters(), None)
        with self.assertRaises(ValueError):
            run_chain([0], 1, spec, FrontendParameters(), ADCParameters(), seed=-1)

    def test_invalid_tone_requests(self):
        for kwargs in (
            {"n_samples": 3, "target_hz": 1000},
            {"n_samples": 16384, "target_hz": 0},
            {"n_samples": 16384, "target_hz": 50000},
            {"n_samples": 16384, "target_hz": 1000, "amplitude_dbfs": 1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                coherent_tone(Spec(), **kwargs)


if __name__ == "__main__":
    unittest.main()
