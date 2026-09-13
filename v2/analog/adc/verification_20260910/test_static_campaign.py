"""Synthetic fixtures test analysis only. Never transistor evidence."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import static_campaign as sc


class StaticCampaignTests(unittest.TestCase):
    def test_centres_are_not_ramp(self):
        centres = sc.grid("centres")
        self.assertEqual(len(centres), 4096)
        self.assertAlmostEqual(centres[0], -.4 + sc.LSB / 2)
        self.assertEqual(len(sc.grid("ramp", 32)), 131073)

    def test_invalid_inputs_rejected(self):
        for value in ([float("nan")], [.401]):
            with self.assertRaises(ValueError):
                sc.grid("smoke", inputs=value)
        with self.assertRaises(ValueError):
            sc.grid("ramp", 8)

    def test_ideal_ramp_has_bounded_quantisation_error(self):
        # Generate exact integer-grid ideal codes, avoiding binary float floor
        # effects at mathematical thresholds. This is NOT circuit data.
        x = sc.grid("ramp", 32)
        codes = np.minimum(np.arange(len(x)) // 32, 4095)
        report = sc.static_metrics(x, codes)
        self.assertEqual(report["status"], "GRID_STATIC_LIMITS_PASS")
        self.assertLess(max(abs(v) for v in report["endpoint_inl_envelope_lsb"]), .07)
        self.assertLessEqual(report["max_transition_bracket_lsb"], .031250000001)

    def test_missing_code_rejected(self):
        x = sc.grid("ramp", 16)
        codes = np.minimum(np.arange(len(x)) // 16, 4095)
        codes[codes == 2048] = 2049
        report = sc.static_metrics(x, codes)
        self.assertEqual(report["status"], "FAIL_UNOBSERVED_CODES")
        self.assertIn(2048, report["unobserved_codes"])

    def test_nonmonotonic_rejected(self):
        self.assertEqual(sc.static_metrics([-.4, 0, .4], [0, 3000, 2999])["status"], "FAIL_NONMONOTONIC_OR_INVALID_CODE")

    def test_nonlinearity_fails(self):
        x = np.asarray(sc.grid("ramp", 32))
        thresholds = -.4 + np.arange(1, 4096) * sc.LSB
        thresholds += 2 * sc.LSB * np.sin(np.linspace(0, np.pi, 4095))
        codes = np.searchsorted(thresholds, x, side="right")
        self.assertEqual(sc.static_metrics(x, codes)["status"], "STATIC_LIMIT_FAIL")

    def test_endpoint_gain_normalisation_is_not_code_calibration(self):
        x = np.asarray(sc.grid("ramp", 32))
        thresholds = (-.4 + np.arange(1, 4096) * sc.LSB) * .99
        codes = np.searchsorted(thresholds, x, side="right")
        report = sc.static_metrics(x, codes)
        self.assertEqual(report["status"], "GRID_STATIC_LIMITS_PASS")
        # Range-clipped end-code width is large, but is not interior DNL.
        self.assertGreater(report["nominal_lsb_clipped_width_diagnostic"][1], 10)

    def test_actual_output_bus_must_agree_with_log(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "simulation.log").write_text("COSIM_RESULT time_ns=0.000 code=2677 gain_code=0\n")
            values = np.zeros((5, 16))
            values[:, 0] = [0, 11.003e-6, 11.004e-6, 11.020e-6, 12e-6]
            values[2:, 1] = 1.8
            bits = [(2677 >> bit) & 1 for bit in range(11, -1, -1)]
            values[2:, 4:] = np.asarray(bits) * 1.8
            np.savetxt(directory / "waveform.dat", values, header="synthetic fixture", comments="")
            plan = {"plan_sha256": "test", "vdd_v": 1.8}
            sequence = [{"point_id": 0, "input_v": .123, "kind": "retained"}]
            self.assertEqual(sc.analyse_batch(directory, plan, sequence, 0)["status"], "BATCH_COMPLETE_NOT_ADC_QUALIFIED")
            values[2:, 4] = 0
            np.savetxt(directory / "waveform.dat", values, header="synthetic fixture", comments="")
            self.assertEqual(sc.analyse_batch(directory, plan, sequence, 0)["status"], "INCOMPLETE")

    def test_batch_replays_history_and_discards_warmup(self):
        plan = {"batch_size": 2, "required_points": 4, "input_v": [0, .1, .2, .3], "warmup_conversions": 1}
        seq = sc.sequence_for_batch(plan, 2)
        self.assertEqual([s["point_id"] for s in seq], [None, None, 2, None, 3])
        self.assertEqual(seq[0]["input_v"], .1)
        self.assertIn("11.014000000u", sc.pwl_input(seq, .9, 1))

    def test_incomplete_coverage_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            plan = {"stage": "centres", "batch_size": 8, "required_points": 4096,
                    "sources": {}, "input_v": sc.grid("centres")}
            plan["plan_sha256"] = sc.digest(plan)
            sc.write_json(directory / "plan.json", plan)
            with contextlib.redirect_stdout(io.StringIO()):
                report = sc.collect(directory)
            self.assertEqual(report["status"], "INCOMPLETE_COVERAGE")
            self.assertFalse(report["complete_adc_qualified"])
            self.assertEqual(report["completed_points"], 0)
            self.assertEqual(len(report["missing_batches"]), 512)

    def test_mutated_plan_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            plan = {"sources": {}}
            plan["plan_sha256"] = sc.digest(plan)
            plan["added_after_freeze"] = True
            sc.write_json(directory / "plan.json", plan)
            with self.assertRaises(ValueError):
                sc.read_plan(directory)

    def test_changed_analysis_runner_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            plan = {"sources": {"static_campaign.py": {"sha256": "not-the-current-runner"}}}
            plan["plan_sha256"] = sc.digest(plan)
            sc.write_json(directory / "plan.json", plan)
            with self.assertRaisesRegex(ValueError, "runner changed"):
                sc.read_plan(directory)

    def test_timeout_log_does_not_become_conversion_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "simulation.log").write_text("COSIM_RESULT time_ns=0.000 code=2677 gain_code=0\n")
            report = sc.analyse_batch(directory, {"plan_sha256": "test"}, [], None)
            self.assertEqual(report["status"], "INCOMPLETE")
            self.assertEqual(report["raw_codes"], [2677])
            self.assertEqual(report["rows"], [])


if __name__ == "__main__":
    unittest.main()
