import csv
import json
from pathlib import Path
import subprocess
import sys
import unittest


HERE = Path(__file__).resolve().parent


class CdacAssignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(HERE / "generate_assignment.py")], check=True,
                       cwd=HERE, capture_output=True, text=True)
        cls.summary = json.loads((HERE / "assignment_summary.json").read_text())

    def test_summary_passes(self):
        self.assertEqual(self.summary["status"], "PLACEMENT_ASSIGNMENT_PASS")
        for side in ("p_side", "n_side"):
            self.assertTrue(all(self.summary[side]["checks"].values()))

    def test_electrical_counts(self):
        expected = {f"B{bit}": 1 << bit for bit in range(12)} | {"DUMMY": 1}
        for side in ("p_side", "n_side"):
            self.assertEqual(self.summary[side]["counts"], expected)

    def test_csv_rows_and_unique_locations(self):
        for name in ("cdac_p_assignment.csv", "cdac_n_assignment.csv"):
            with (HERE / name).open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 66 * 66)
            positions = {(row["physical_row"], row["physical_col"]) for row in rows}
            self.assertEqual(len(positions), len(rows))
            self.assertEqual(sum(int(row["electrical"]) for row in rows), 4096)

    def test_no_false_physical_claim(self):
        level = self.summary["evidence_level"].lower()
        self.assertIn("not gds", level)
        self.assertFalse(any("pass" in key.lower() for key in (
            "drc", "lvs", "pex") if key in self.summary))


if __name__ == "__main__":
    unittest.main()
