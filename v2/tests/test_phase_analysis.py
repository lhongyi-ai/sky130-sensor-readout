import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location("phase_analysis",Path(__file__).resolve().parents[1]/"integration/qualify_phases.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PhaseAnalysisTests(unittest.TestCase):
    def test_interpolated_crossing_not_sample_index(self):
        time = np.array([0.,1.,2.,3.])
        signal = np.array([0.,0.,2.,0.])
        np.testing.assert_allclose(module.crossings(time,signal,.5,True),[1.25])
        np.testing.assert_allclose(module.crossings(time,signal,.5,False),[2.75])

    def test_missing_phase_edge_is_error(self):
        values = np.zeros((100,7))
        values[:,0] = np.linspace(0,15e-6,100)
        with self.assertRaises(ValueError):
            module.measure(values,1.8)

    def test_recorded_complete_45pvt_result_has_no_skips(self):
        # Pure analysis test: physical evidence exists only after the simulator
        # suite has run; do not manufacture it or pass a skipped evidence check.
        import json
        path = Path(__file__).resolve().parents[1]/"integration/results/phase_qualification.json"
        if not path.exists():
            self.skipTest("phase evidence test requires a completed physical simulation suite")
        report = json.loads(path.read_text())
        self.assertEqual(len(report["results"]),45)
        cases = {(r["corner"],r["vdd_v"],r["temperature_c"]) for r in report["results"]}
        self.assertEqual(len(cases),45)
        self.assertFalse(report["full_adc_qualified"])


if __name__ == "__main__":
    unittest.main()
