import hashlib
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


class EvidenceTests(unittest.TestCase):
    def test_diagnostic_budget_and_manifests(self):
        diagnostics = HERE / "diagnostics"
        if not diagnostics.exists():
            return
        runs = sorted(p for p in diagnostics.iterdir() if p.is_dir())
        self.assertLessEqual(len(runs), 12)
        for run in runs:
            manifest = json.loads((run / "evidence_manifest.json").read_text())
            self.assertEqual(manifest["version"], 1)
            for name, expected in manifest["files"].items():
                path = run / name
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, expected["size_bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected["sha256"])

    def test_no_hidden_ideal_internal_source(self):
        for path in HERE.glob("candidate_*.spice"):
            text = path.read_text().lower()
            self.assertNotIn("behavioral", text)
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("*"):
                    continue
                self.assertFalse(stripped.startswith(("b", "e", "f", "g", "h")), line)

    def test_frozen_acceptance_values(self):
        text = (HERE / "run_diagnostic.py").read_text()
        self.assertIn("LSB = 0.8 / 4096", text)
        self.assertIn("ACQ_WINDOW = 2.476847754e-6", text)
        self.assertIn("static_error <= 1.0", text)
        self.assertIn("acq_error <= LSB / 4", text)

    def test_qualification_does_not_hide_dynamic_failure(self):
        path = HERE / "qualification.json"
        if not path.exists():
            return
        result = json.loads(path.read_text())
        self.assertTrue(result["same_source_all_three_gains"])
        self.assertTrue(result["all_three_gain_static_gate_pass"])
        self.assertFalse(result["all_three_gain_dynamic_gate_pass"])
        self.assertFalse(result["formal_stability_gate_pass"])
        self.assertFalse(result["pvt_45_screen_allowed"])
        self.assertFalse(result["physical_layoutability_gate_pass"])
        self.assertFalse(result["full_frontend_qualified"])
        self.assertFalse(result["full_chip_qualified"])
        self.assertEqual(result["candidate_sha256"], hashlib.sha256((HERE / result["candidate_path"]).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
