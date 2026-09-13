"""Synthetic evidence-integrity tests only: no PDK, simulator or old result writes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measurement_evidence import (MANIFEST_NAME, require_nominal_or_fixed_calibration,
                                  snapshot_calibration, verify_manifest, write_manifest,
                                  write_analysis)


class MeasurementGuardsTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.folder=Path(self.temporary.name)/'experiment'
        self.folder.mkdir()
        for name,value in {'experiment_config.json':'{"gain":16}', 'sampling.spice':'original deck',
                           'sampling.dat':'time value\n0 0\n1 1\n',
                           'frontend_pdk_snapshot.spice':'original core',
                           'summary.json':'{"test":"sampling"}'}.items():
            (self.folder/name).write_text(value)

    def tearDown(self):
        self.temporary.cleanup()

    def freeze(self):
        return write_manifest(self.folder, required=['experiment_config.json','sampling.dat'])

    def test_nominal_or_fixed_calibration(self):
        require_nominal_or_fixed_calibration(1.8,27,None)
        require_nominal_or_fixed_calibration(1.62,85,'nominal/summary.json')
        for vdd,temp in [(1.62,27),(1.8,85),(1.98,-20)]:
            with self.subTest(vdd=vdd,temp=temp),self.assertRaisesRegex(ValueError,'per-condition refitting'):
                require_nominal_or_fixed_calibration(vdd,temp,None)

    def test_changed_config_raw_deck_and_core_are_rejected(self):
        self.freeze()
        self.assertTrue(verify_manifest(self.folder))
        for name in ['experiment_config.json','sampling.dat','sampling.spice','frontend_pdk_snapshot.spice']:
            path=self.folder/name
            original=path.read_bytes()
            path.write_bytes(original+b'changed')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'changed or is missing'):
                verify_manifest(self.folder)
            path.write_bytes(original)

    def test_missing_raw_is_rejected(self):
        self.freeze()
        (self.folder/'sampling.dat').unlink()
        with self.assertRaisesRegex(ValueError,'changed or is missing'):
            verify_manifest(self.folder)

    def test_calibration_is_frozen_and_tampering_rejected(self):
        calibration=Path(self.temporary.name)/'nominal'
        calibration.mkdir()
        (calibration/'summary.json').write_text('{"calibration_coefficients":[1.01,0.001]}')
        (calibration/'frontend_pdk_snapshot.spice').write_text('same core')
        summary,_=snapshot_calibration(calibration/'summary.json',self.folder)
        frozen=summary.read_bytes()
        self.freeze()
        (calibration/'summary.json').write_text('external source later changed')
        self.assertEqual(summary.read_bytes(),frozen)
        self.assertTrue(verify_manifest(self.folder))
        summary.write_text('changed frozen coefficients')
        with self.assertRaisesRegex(ValueError,'changed or is missing'):
            verify_manifest(self.folder)

    def test_legacy_is_explicitly_unverified(self):
        self.assertFalse(verify_manifest(self.folder))

    def test_manifest_never_overwritten_and_paths_cannot_escape(self):
        self.freeze()
        with self.assertRaises(FileExistsError):
            self.freeze()
        path=self.folder/MANIFEST_NAME
        manifest=json.loads(path.read_text())
        manifest['files']['../outside']={'sha256':'0'*64,'size_bytes':0}
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'direct child'):
            verify_manifest(self.folder)

    def test_new_analysis_preserves_original_evidence(self):
        self.freeze()
        original=(self.folder/'summary.json').read_bytes()
        report=write_analysis(self.folder,{'new_measurement':1})
        self.assertTrue(report.is_file())
        self.assertEqual((self.folder/'summary.json').read_bytes(),original)
        self.assertTrue(verify_manifest(self.folder))


if __name__=='__main__':
    unittest.main()
