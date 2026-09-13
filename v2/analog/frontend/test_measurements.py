import tempfile
import unittest
from pathlib import Path
import numpy as np
from measurements import checked_data, interval_stats
from run_frontend import validate_log

class MeasurementsTest(unittest.TestCase):
    def test_nonuniform_samples_are_time_weighted(self):
        t=np.array([0,.01,.02,.03,1.])
        mean,ripple=interval_stats(t,t,0,1)
        self.assertAlmostEqual(mean,.5)
        self.assertAlmostEqual(ripple,1)
        self.assertNotAlmostEqual(float(np.mean(t)),mean)

    def test_requested_endpoint_is_interpolated(self):
        mean,ripple=interval_stats(np.array([1.,4.,10.]),np.array([2.,8.,20.]),1,5)
        self.assertAlmostEqual(mean,6)
        self.assertAlmostEqual(ripple,8)

    def test_incomplete_or_nonfinite_data_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.dat'
            p.write_text('t v\n0 1\n.5 2\n')
            with self.assertRaises(ValueError): checked_data(p,stop=1)
            p.write_text('t v\n0 1\n1 nan\n')
            with self.assertRaises(ValueError): checked_data(p,stop=1)

    def test_aborted_simulation_is_not_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run.log'
            p.write_text('tran simulation(s) aborted\nngspice-47 done\n')
            with self.assertRaises(RuntimeError): validate_log(p)
            p.write_text('ngspice-47 done\n')
            validate_log(p)

    def test_uncovered_reference_interval_rejected(self):
        with self.assertRaises(ValueError):
            interval_stats(np.array([1.,2.]),np.array([0.,0.]),0,2)

if __name__=='__main__': unittest.main()
