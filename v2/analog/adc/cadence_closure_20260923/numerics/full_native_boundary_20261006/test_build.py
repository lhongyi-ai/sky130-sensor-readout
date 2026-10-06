"""Counterexamples for completeness and stimulus equivalence; no EDA results."""
import unittest
from build import CONSTANTS, PREFIX, STOP, PORTS, PHASE_PORTS, ramp, verify_boundary, audit_native


class BoundaryTests(unittest.TestCase):
    def rows(self):
        times = [0., 1.885e-6, 1.8855e-6, 1.886e-6, 4.0625e-6, 4.063e-6, 4.0635e-6, STOP]
        return [dict(time=t, **{PREFIX + n: v for n, v in CONSTANTS.items()},
                     **{PREFIX + 'rst_n_e': ramp(t, 1.885e-6), PREFIX + 'sample_cmd_e': ramp(t, 4.0625e-6)}) for t in times]

    def test_complete_known_boundary(self):
        self.assertEqual(max(verify_boundary(self.rows())['max_errors_V'].values()), 0.)

    def test_short_domain_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'complete'):
            verify_boundary(self.rows()[:-1])

    def test_changed_reset_is_rejected(self):
        rows = self.rows()
        rows[2][PREFIX + 'rst_n_e'] = 1.8
        with self.assertRaisesRegex(ValueError, 'not equivalent'):
            verify_boundary(rows)

    def test_changed_trial_bit_is_rejected(self):
        rows = self.rows()
        rows[4][PREFIX + 'trial_e[11]'] = 1.8
        with self.assertRaisesRegex(ValueError, 'not equivalent'):
            verify_boundary(rows)

    def native(self):
        names = ['XADC_XPRE_%d' % i for i in range(87)] + ['XADC_%d' % i for i in range(606)]
        adc = '\n'.join(n + ' (A B C D) model w=1u' for n in names)
        phase = '\n'.join('XPHASE_%d (A B C D) model w=1u' % i for i in range(48))
        return 'subckt sensor_adc_reset1 (' + ' '.join(PORTS) + ')\n' + adc + '\nends sensor_adc_reset1\nsubckt sensor_phases (' + ' '.join(PHASE_PORTS) + ')\n' + phase + '\nends sensor_phases\n'

    def test_all_devices_retained(self):
        self.assertEqual(sum(audit_native(self.native()).values()), 741)

    def test_netlister_alignment_whitespace_is_valid(self):
        self.assertEqual(sum(audit_native(self.native().replace(') model', ')          model')).values()), 741)

    def test_reduced_circuit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'count'):
            audit_native(self.native().replace('XADC_XPRE_0 (A B C D) model w=1u\n', ''))

    def test_duplicate_device_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'uniqueness'):
            audit_native(self.native().replace('XADC_1 (', 'XADC_0 ('))

    def test_changed_port_order_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'port contract'):
            audit_native(self.native().replace('(INP INN Q', '(INN INP Q'))


if __name__ == '__main__':
    unittest.main()
