import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("acceleration", HERE / "accelerate.py")
acceleration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceleration)
GATE_SPEC = importlib.util.spec_from_file_location("acceleration_gate", HERE / "gate.py")
acceleration_gate = importlib.util.module_from_spec(GATE_SPEC)
GATE_SPEC.loader.exec_module(acceleration_gate)


class AccelerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deck, cls.vectors, cls.reference, cls.summary = acceleration.load_reference()
        cls.base = acceleration.known_traces(cls.vectors, cls.reference)

    def test_event_compression_is_below_numeric_gate_at_every_saved_point(self):
        report = acceleration.reconstructed_source_error(self.vectors, self.reference, self.base)
        self.assertEqual(report["status"], "PASS")
        self.assertLessEqual(report["maximum_v"], 0.05 * acceleration.LSB)

    def test_rtl_recurrence_recreates_all_known_trial_and_data_edges(self):
        predicted = acceleration.predicted_traces(self.base, self.summary["expected_codes"])
        report = acceleration.reconstructed_source_error(self.vectors, self.reference, predicted)
        self.assertEqual(report["status"], "PASS")

    def test_decks_remove_only_testbench_bridge(self):
        for mode in ("known", "predicted"):
            deck, _, _, expected, _, removed = acceleration.make_deck(mode)
            self.assertEqual(len(removed), 6)
            self.assertNotIn(" d_cosim ", deck)
            self.assertNotIn("Ainputs ", deck)
            self.assertNotIn("Aoutputs ", deck)
            self.assertIn("XPHASE sample", deck)
            self.assertIn("XADC inp inn decision decision_b", deck)
            self.assertNotIn("VTRACE_decision ", deck)
            self.assertNotIn("VTRACE_decision_b ", deck)
            self.assertEqual(len(expected), 6)

    def test_real_reference_accepts_all_expected_decisions(self):
        report = acceleration.comparator_certificate(
            self.reference, self.vectors, self.summary["expected_codes"]
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["accepted_decisions"], 72)

    def test_wrong_prediction_is_rejected(self):
        wrong = list(self.summary["expected_codes"])
        wrong[0] ^= 1
        report = acceleration.comparator_certificate(self.reference, self.vectors, wrong)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["accepted_decisions"], 71)

    def test_predicted_inputs_are_new_centres_in_range(self):
        self.assertFalse(any(word in self.summary["expected_codes"] for word in acceleration.PREDICTED_WORDS))
        values = [-0.4 + (word + 0.5) * acceleration.LSB for word in acceleration.PREDICTED_WORDS]
        self.assertTrue(all(-0.4 < value < 0.4 for value in values))

    def test_long_campaign_fails_closed_after_numeric_gate_failure(self):
        report = acceleration_gate.evaluate_gate()
        self.assertTrue(report["independent_prediction_72_of_72_pass"])
        self.assertFalse(report["numeric_equivalence_0_05_lsb_pass"])
        self.assertFalse(report["long_all_code_campaign_allowed"])


if __name__ == "__main__":
    unittest.main()
