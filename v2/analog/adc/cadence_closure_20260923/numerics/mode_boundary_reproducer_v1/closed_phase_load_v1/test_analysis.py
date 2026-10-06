import unittest
from analyze import compare,norm
class Tests(unittest.TestCase):
 def test_narrow_edge_retained(self):
  a=[{'time':0.,'x':0.},{'time':.49,'x':0.},{'time':.5,'x':1.},{'time':1.,'x':1.}]
  b=[{'time':0.,'x':0.},{'time':.5,'x':0.},{'time':.51,'x':1.},{'time':1.,'x':1.}]
  r=compare(a,b,{'x':'V'});self.assertEqual(r['signals']['x']['max_abs_difference'],1.)
 def test_incomplete_tail_not_complete(self):
  r=compare([{'time':0.,'x':0.},{'time':1.,'x':1.}],[{'time':0.,'x':0.},{'time':.6,'x':.6}],{'x':'V'})
  self.assertFalse(r['both_complete_same_saved_domain']);self.assertEqual(r['interval_s'],[0.,.6])
 def test_mode_step_not_ramp(self):
  a=[{'time':0.,'x':0.},{'time':.4,'x':1.},{'time':1.,'x':1.}]
  b=[{'time':0.,'x':0.},{'time':.6,'x':1.},{'time':1.,'x':1.}]
  self.assertEqual(compare(a,b,{'x':'-enum'})['signals']['x']['max_abs_difference'],1.)
 def test_numerical_normalization_does_not_hide_method_or_device(self):
  self.assertEqual(norm('reltol=1e-5 maxstep=2n method=gear2only'),norm('reltol=1e-6 maxstep=1n method=gear2only'))
  self.assertNotEqual(norm('r=1 method=gear2only'),norm('r=2 method=gear2only'))
  self.assertNotEqual(norm('method=gear2only'),norm('method=traponly'))
if __name__=='__main__':unittest.main()
