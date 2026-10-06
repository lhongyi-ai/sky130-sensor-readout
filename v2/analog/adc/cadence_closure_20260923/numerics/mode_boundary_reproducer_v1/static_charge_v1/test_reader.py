from pathlib import Path
import tempfile,unittest
from inspect_outputs import read_dc
class DCReader(unittest.TestCase):
 def parse(self,values):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'s.dc';p.write_text('HEADER\n"analysis name" "dc_test"\nSWEEP\n"VDELTA" "V"\nTRACE\n"qg" "Coul"\n"rev" "-enum"\nVALUE\n'+values+'\nEND\n');return read_dc(p)
 def test_signed_charge_and_descending_axis_preserved(self):
  h,a,s,r=self.parse('"VDELTA" 1e-6\n"qg" -2e-14\n"rev" 1\n"VDELTA" -1e-6\n"qg" -3e-14\n"rev" 0')
  self.assertEqual(a,'VDELTA');self.assertEqual(r[0]['qg'],-2e-14);self.assertEqual(r[1]['rev'],0)
 def test_missing_charge_not_zero_filled(self):
  with self.assertRaisesRegex(ValueError,'IncompleteDCrow'):self.parse('"VDELTA" -1e-6\n"rev" 0\n"VDELTA" 1e-6\n"qg" 3e-14\n"rev" 1')
 def test_duplicate_bias_not_silently_removed(self):
  with self.assertRaisesRegex(ValueError,'NonmonotonicDCaxis'):self.parse('"VDELTA" 0\n"qg" -2e-14\n"rev" 0\n"VDELTA" 0\n"qg" -3e-14\n"rev" 1')
if __name__=='__main__':unittest.main()
