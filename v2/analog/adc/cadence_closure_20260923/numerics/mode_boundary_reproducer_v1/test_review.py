import unittest
from review import compare_samples,configuration
class ReviewTests(unittest.TestCase):
 def test_narrow_body_edge_is_retained(self):
  a=[{'time':t,'b':v,'e':0.} for t,v in [(0,0),(.49,0),(.5,1),(.51,0),(1,0)]]
  b=[{'time':0.,'b':0.,'e':0.},{'time':1.,'b':0.,'e':0.}]
  r=compare_samples(a,b,{'b':'V','e':'-enum'})
  self.assertEqual(r['signals']['b']['maximum_absolute_difference'],1.)
  self.assertEqual(r['all_union_points'],5)
 def test_enum_not_linearly_interpolated(self):
  a=[{'time':0.,'e':0.},{'time':1.,'e':1.}]
  b=[{'time':0.,'e':0.},{'time':.9,'e':0.},{'time':1.,'e':1.}]
  self.assertEqual(compare_samples(a,b,{'e':'-enum'})['signals']['e']['maximum_absolute_difference'],0.)
 def test_missing_tail_not_passed(self):
  a=[{'time':0.,'v':0.},{'time':.7,'v':0.}];b=[{'time':0.,'v':0.},{'time':1.,'v':0.}]
  self.assertFalse(compare_samples(a,b,{'v':'V'})['full_saved_intervals_equal'])
 def test_physics_and_method_changes_detected(self):
  a='X (D G S B) pfet w=32u\noptions reltol=1e-5 method=gear2only'
  self.assertEqual(configuration(a),configuration(a.replace('1e-5','1e-6')))
  self.assertNotEqual(configuration(a),configuration(a.replace('32u','33u')))
  self.assertNotEqual(configuration(a),configuration(a.replace('gear2only','traponly')))
  self.assertEqual(configuration(a,True),configuration(a.replace('gear2only','traponly'),True))
if __name__=='__main__':unittest.main()
