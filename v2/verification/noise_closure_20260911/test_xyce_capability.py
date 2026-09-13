import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


class XyceCapabilityEvidenceTest(unittest.TestCase):
    def test_identity_report_does_not_claim_noise(self):
        report = json.loads((HERE / "xyce_capability.json").read_text())
        self.assertEqual(report["status"], "IDENTITY_ONLY_NOT_NOISE_QUALIFIED")
        self.assertFalse(report["adc_noise_qualified"])
        self.assertIn("7.10", report["official_reference"]["title"])
        self.assertIn("no Y", report["official_reference"]["review_result"])

    def test_installed_version_is_recorded(self):
        report = json.loads((HERE / "xyce_capability.json").read_text())
        self.assertEqual(report["version"]["returncode"], 0)
        combined = report["version"]["stdout"] + report["version"]["stderr"]
        self.assertIn("Xyce Release 7.10-opensource", combined)


if __name__ == "__main__":
    unittest.main()
