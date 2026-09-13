import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integration"))
try:
    spec = importlib.util.spec_from_file_location("adc_cosim_analysis", ROOT / "integration/run_adc_cosim.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
finally:
    sys.path.pop(0)


class IntegrationProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.report = {"status": "LIVE_RTL_SPICE_BRIDGE_PASS", "backend": "verilator",
                       "vdd_v": 1.8, "source_sha256": {}}
        for name in ("integration/cosim_controller.v", "integration/qualify_cosim.py", "rtl/sar_controller.v"):
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(name)
            self.report["source_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_matching_sources_accepted(self):
        module.validate_bridge(self.report, self.root, 1.8)

    def test_modified_rtl_rejected(self):
        (self.root / "rtl/sar_controller.v").write_text("changed")
        with self.assertRaises(ValueError):
            module.validate_bridge(self.report, self.root, 1.8)

    def test_missing_digest_rejected(self):
        self.report["source_sha256"].pop("integration/cosim_controller.v")
        with self.assertRaises(ValueError):
            module.validate_bridge(self.report, self.root, 1.8)

    def test_other_supply_rejected(self):
        with self.assertRaises(ValueError):
            module.validate_bridge(self.report, self.root, 1.62)


if __name__ == "__main__":
    unittest.main()
