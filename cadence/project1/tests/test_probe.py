"""Behavior tests use synthetic temporary data, never a Cadence installation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "probe" / "probe.py"
spec = importlib.util.spec_from_file_location("p1probe", MODULE)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p1-probe-test-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def start(self):
        # Empty PATH avoids depending on installed EDA tools or checking a license.
        with patch.dict(p.os.environ, {"PATH": ""}), patch.object(p, "KNOWN_PDK", self.root / "missing"):
            return p.probe(self.root, self.root / "cds.lib", [])

    def test_missing_cadence_returns_useful_partial_report(self):
        run = self.start()
        target, summary = p.collect(self.root)
        self.assertEqual(summary["status"], "PARTIAL_REPORT")
        self.assertEqual(summary["simulation"], "NOT_RUN")
        with zipfile.ZipFile(target) as z:
            manifest_name = next(n for n in z.namelist() if n.endswith("report_manifest.json"))
            manifest = json.loads(z.read(manifest_name))
            for name, digest in manifest["sha256"].items():
                self.assertEqual(digest, p.hashlib.sha256(z.read(run.name + "/" + name)).hexdigest())

    def test_completed_probe_is_not_simulation_pass_and_secrets_excluded(self):
        run = self.start()
        (run / "cadence_report.txt").write_text(
            'RUN_ID\t"' + run.name + '"\nCORE_METADATA_OK\tt\n'
            'password=do-not-include\nPROBE_COMPLETE\t"' + run.name + '"\n')
        (run / "unrelated_license_file.txt").write_text("must not be packaged")
        target, summary = p.collect(self.root)
        self.assertEqual(summary["status"], "METADATA_COLLECTED_REQUIRES_REVIEW")
        self.assertEqual(summary["license_checkout"], "NOT_TESTED")
        with zipfile.ZipFile(target) as z:
            self.assertFalse(any("unrelated" in n or "cadence_paths" in n for n in z.namelist()))
            self.assertFalse(any(b"do-not-include" in z.read(n) for n in z.namelist()))

    def test_wrong_run_completion_is_rejected(self):
        run = self.start()
        (run / "cadence_report.txt").write_text('CORE_METADATA_OK\tt\nPROBE_COMPLETE\t"old-run"\n')
        _, summary = p.collect(self.root)
        self.assertFalse(summary["cadence_probe_complete"])

    def test_repeat_probe_preserves_previous_run_and_project(self):
        project = self.root / "project1"
        project.mkdir()
        existing = project / "design.txt"
        existing.write_text("USER DESIGN")
        before = existing.read_bytes()
        run1, run2 = self.start(), self.start()
        self.assertNotEqual(run1, run2)
        self.assertTrue((run1 / "linux_report.json").exists())
        self.assertEqual(existing.read_bytes(), before)
        self.assertEqual([x.name for x in project.iterdir()], ["design.txt"])

    def test_cds_cycle_missing_include_and_undefined_variable(self):
        (self.root / "cds.lib").write_text(
            'INCLUDE nested.lib\nDEFINE project1 "project with spaces"\nSOFTINCLUDE missing.lib\n'
            'INCLUDE $P1_TEST_NOT_SET/a.lib\n')
        (self.root / "nested.lib").write_text('INCLUDE cds.lib\nDEFINE sky130_fd_sc_hd cells\n')
        result = p.cds_inventory(self.root / "cds.lib")
        self.assertEqual(len(result["definitions"]), 2)
        self.assertTrue(any(x["status"] == "UNRESOLVED_VARIABLE" for x in result["notes"]))
        self.assertFalse(result["scan_limit_reached"])
        self.assertEqual(Path(result["definitions"][0]["path"]).resolve(), (self.root / "project with spaces").resolve())

    def test_model_report_has_names_not_model_parameters(self):
        model = self.root / "test.scs"
        model.write_text('section tt\nmodel nmos bsim4 vth0=0.123456789\n'
                         'statistics {\nsubckt foo d g s b\n')
        data = p.model_metadata(model)
        self.assertEqual(data["sections"], ["tt"])
        self.assertEqual(data["subcircuits"], ["foo"])
        self.assertTrue(data["statistics_keyword"])
        self.assertNotIn("0.123456789", json.dumps(data))

    def test_models_prioritized_over_many_cell_models(self):
        cells = self.root / "cells"
        cells.mkdir()
        for i in range(170):
            (cells / ("cap_%03d.spice" % i)).write_text(".subckt cap a b\n")
        models = self.root / "models" / "spectre"
        models.mkdir(parents=True)
        (models / "sky130.scs").write_text("section tt\nendsection tt\n")
        data = p.scan_pdk([self.root])
        self.assertTrue(any(m["sections"] == ["tt"] for m in data["model_headers"]))

    def test_missing_mapping_and_sections_are_explicit(self):
        run = self.start()
        (run / "cadence_report.txt").write_text('CORE_METADATA_OK\tt\nPROBE_COMPLETE\t"' + run.name + '"\n')
        _, summary = p.collect(self.root)
        self.assertIn("NMOS_SPECTRE_CDF_MAPPING_NOT_COLLECTED", summary["issues"])
        self.assertIn("MODEL_SECTION_ENTRYPOINT_NOT_COLLECTED", summary["issues"])

    def test_noise_help_filtered_before_truncation(self):
        completed = p.subprocess.CompletedProcess([], 0, "x" * 9000 + "\nnoisefmax Noise bandwidth\n")
        with patch.object(p.subprocess, "run", return_value=completed):
            result = p.run_readonly(["spectre", "-h", "tran"], "noise")
        self.assertIn("noisefmax", result["output"])

    def test_invalid_active_run_cannot_escape_package(self):
        (self.root / "active_run.json").write_text('{"run_id":"../../outside"}')
        with self.assertRaises(ValueError):
            p.active_run(self.root)

    def test_collect_before_probe_fails_clearly(self):
        with self.assertRaises(FileNotFoundError):
            p.collect(self.root)


if __name__ == "__main__":
    unittest.main()
