"""No-simulation tests for the repaired-bridge immutable full-grid plan."""
import json
import unittest

import trace_replay as tr
from resume_campaign import validate_resume, verify_fixed_evidence


class ResumeGateTests(unittest.TestCase):
    def test_grid_not_reduced(self):
        plan = validate_resume(tr.HERE / 'campaigns/fixed_ramp32')
        self.assertEqual(plan['required_points'], 131073)
        self.assertEqual(plan['steps_per_lsb'], 32)
        self.assertEqual(plan['input_v'][0], -.4)
        self.assertEqual(plan['input_v'][-1], .4)

    def test_execution_rejects_failed_numeric_gate(self):
        with self.assertRaisesRegex(ValueError, 'NUMERICAL_GATE_BLOCKED'):
            validate_resume(tr.HERE / 'campaigns/fixed_ramp32', for_execution=True)

    def test_repair_is_bounded_not_all_adc(self):
        evidence = verify_fixed_evidence(tr.HERE / 'results/20260911T081221912898Z_bridge_fixed')
        self.assertEqual(evidence['handshake']['status'], 'BOUNDED_STATUS_PORTS_PASS')
        self.assertFalse(evidence['complete_adc_qualified'])
        self.assertFalse(evidence['full_interface_qualified'])

    def test_plan_cannot_regenerate_old_bad_binary(self):
        campaign = tr.HERE / 'campaigns/fixed_ramp32'
        record = json.loads((campaign / 'build/binary.json').read_text())
        self.assertTrue(record['local_repaired_shim'])
        self.assertNotEqual(record['sha256'], tr.sc.sha(tr.CAMPAIGN / 'build/cosim_controller.so'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
