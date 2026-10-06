import tempfile
import unittest
from pathlib import Path
from psf_stream import Trace
from compare_full_adc_stream import union_compare, fixed_configuration
from measurement_domain import schedule


class StreamTests(unittest.TestCase):
    def test_explicit_current_and_enum_schema_without_zero_fill(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.tran';p.write_text('TRACE\n" 1" GROUP 1\n"body" "V" PROP(\n"units" "V"\n)\n" 2" GROUP 1\n"flow" "I" PROP(\n"units" "A"\n)\n" 3" GROUP 1\n"reverse" "-enum" PROP(\n"units" "-enum"\n)\nVALUE\n"time" 0\n" 1" 1.8\n" 2" -1e-6\n" 3" 1\n')
            self.assertEqual(list(Trace(p).rows()),[{'time':0.,'body':1.8}])
            self.assertEqual(list(Trace(p,accepted_types=('V','I','-enum')).rows()),[{'time':0.,'body':1.8,'flow':-1e-6,'reverse':1.}])
            p.write_text(p.read_text().replace('" 3" 1\n',''))
            with self.assertRaises(ValueError):list(Trace(p,accepted_types=('V','I','-enum')).rows())
    def test_frozen_testbench_finish_schedule(self):
        self.assertEqual(schedule(2)['finish_ps'],30947500)
        self.assertEqual(schedule(12)['finish_ps'],130947500)
    def test_planned_end_interpolation_and_unmatched_tail_audit(self):
        a=[{'time':0.,'v':0.},{'time':1.,'v':1.},{'time':2.,'v':1.}]
        b=[{'time':0.,'v':0.},{'time':.7,'v':.7},{'time':1.5,'v':1.5}]
        r=union_compare(a,b,{'v':('v',)},domain_end=.9)
        self.assertTrue(r['planned_measurement_domain']['fully_covered'])
        self.assertLess(r['planned_measurement_domain']['channels']['v']['max_abs_V'],1e-15)
        self.assertGreater(r['channels']['v']['max_abs_V'],.4)
        self.assertTrue(r['outside_planned_domain_audit']['unpaired_tail_present'])
    def test_domain_cannot_hide_internal_switch_or_missing_end(self):
        a=[{'time':0.,'v':0.},{'time':.1,'v':1.},{'time':.1001,'v':0.},{'time':.5,'v':0.}]
        b=[{'time':0.,'v':0.},{'time':1.,'v':0.}]
        r=union_compare(a,b,{'v':('v',)},domain_end=.9)
        self.assertFalse(r['planned_measurement_domain']['fully_covered'])
        self.assertEqual(r['planned_measurement_domain']['channels']['v']['max_abs_V'],1.)
    def test_only_precision_configuration_is_ignored(self):
        a='include "same.scs" section=tt\nopts options temp=27 reltol=1e-5 vabstol=1e-8 iabstol=1e-13\nt tran stop=40u maxstep=2n relref=sigglobal'
        b=a.replace('1e-5','1e-6').replace('1e-8','1e-9').replace('1e-13','1e-14').replace('2n','1n')
        self.assertEqual(fixed_configuration(a),fixed_configuration(b))
        self.assertNotEqual(fixed_configuration(a),fixed_configuration(b.replace('sigglobal','alllocal')))
        self.assertNotEqual(fixed_configuration(a),fixed_configuration(b.replace('temp=27','temp=30')))
        self.assertNotEqual(fixed_configuration(a),fixed_configuration(b.replace('same.scs','other.scs')))
    def test_string_solver_header_is_retained(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.tran';p.write_text('HEADER\n"method" "gear2only"\n"reltol" 1e-7\nTRACE\n"v" "V"\nVALUE\n"time" 0\n"v" 1\n')
            t=Trace(p);list(t.rows())
            self.assertEqual(t.header['method'],'gear2only')
            self.assertEqual(t.header['reltol'],1e-7)
    def test_alias_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.tran";p.write_text('TRACE\n" 1" GROUP 1\n"foo" "V"\nVALUE\n"time" 0\n" 1" 1\n"time" 1\n" 1" 2\n')
            self.assertEqual(list(Trace(p,{"foo"}).rows()),[{"time":0.,"foo":1.},{"time":1.,"foo":2.}])
    def test_union_catches_narrow_switch_peak(self):
        a=[{"time":t,"v":v} for t,v in [(0,0),(.5,0),(.50001,1),(.50002,0),(1,0)]]
        b=[{"time":0.,"v":0.},{"time":1.,"v":0.}]
        r=union_compare(a,b,{"test":("v",)})
        self.assertEqual(r["channels"]["test"]["max_abs_V"],1.)
        self.assertTrue(r["full_intervals_equal"])
    def test_missing_tail_cannot_be_hidden(self):
        a=[{"time":0.,"v":0.},{"time":1.,"v":0.}]
        b=[{"time":0.,"v":0.},{"time":2.,"v":0.}]
        self.assertFalse(union_compare(a,b,{"v":("v",)})["full_intervals_equal"])
    def test_different_same_time_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.tran";p.write_text('TRACE\n"foo" "V"\nVALUE\n"time" 0\n"foo" 1\n"time" 0\n"foo" 2\n')
            with self.assertRaises(ValueError):list(Trace(p).rows())


if __name__=="__main__":unittest.main()
