#!/usr/bin/env python3
"""Analytic controls test sign/normalization only; never substitutes for EDA."""
import math, tempfile, unittest
from pathlib import Path
from analyze_ac import port_column, read_ac

class AnalysisTests(unittest.TestCase):
    def test_parallel_resistor_capacitor_and_nonunit_complex_drive(self):
        f=1000.; cap=2e-12; conductance=1e-3; voltage=0.5+0.75j
        current=(conductance+1j*2*math.pi*f*cap)*voltage
        row={'freq':f,'D':voltage,'G':0j,'SB':0j,'VD:p':-current,'VG:p':0j,'VS:p':current}
        r=port_column(row)
        self.assertAlmostEqual(r['ports']['D']['G_kD_S'],conductance)
        self.assertAlmostEqual(r['ports']['D']['C_effective_kD_F']/cap,1.)
        self.assertAlmostEqual(r['ports']['SB']['C_effective_kD_F']/cap,-1.)
        self.assertEqual(r['KCL_sum_external_device_currents_A'],[0.,0.])

    def test_reject_nonzero_other_port_excitation(self):
        row={'freq':1000.,'D':1j,'G':1e-3+0j,'SB':0j,'VD:p':0j,'VG:p':0j,'VS:p':0j}
        with self.assertRaises(ValueError): port_column(row)

    def test_sweep_properties_not_second_axis_and_duplicate_signal_rejected(self):
        t='SWEEP\n"freq" "sweep" PROP(\n"units" "Hz"\n)\nTRACE\n"D" "V"\nVALUE\n"freq" 1000\n"D" (1 0)\n"freq" 10000\n"D" (1 0)\nEND\n'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'actual.ac'; p.write_text(t)
            schema,rows=read_ac(p); self.assertEqual(len(rows),2); self.assertEqual(schema,{'D':'V'})
            p.write_text(t.replace('"D" (1 0)\n','"D" (1 0)\n"D" (2 0)\n',1))
            with self.assertRaises(ValueError): read_ac(p)

    def test_missing_complex_signal_is_not_zero_filled(self):
        t='SWEEP\n"freq" "sweep"\nTRACE\n"D" "V"\n"G" "V"\nVALUE\n"freq" 1000\n"D" (1 0)\n"freq" 10000\n"D" (1 0)\nEND\n'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.ac'; p.write_text(t)
            with self.assertRaises(ValueError): read_ac(p)

if __name__ == '__main__': unittest.main()
