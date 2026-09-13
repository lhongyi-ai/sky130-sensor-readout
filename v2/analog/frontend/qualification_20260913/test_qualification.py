"""Independent checks for the bilateral return-ratio convention and evidence."""
import unittest
from pathlib import Path
import json, hashlib
import numpy as np
from run_qualification import instrument, HERE

class QualificationChecks(unittest.TestCase):
    def test_bilateral_known_two_port(self):
        # Direct nodal equations: Ye*ve+k3*vf-if=iinj;
        # k1*ve+Yf*vf+if=0; ve-vf=vinj. Test complex bilateral case.
        for s in (0j,1j,1e3j):
            ye=2+s*.003;yf=3+s*.007;k1=11/(1+s*.04);k3=1.7/(1+s*.02)
            total=ye+yf+k1+k3
            A=-(k1+yf)/total;B=(ye*yf-k1*k3)/total;C=1/total;D=(k3+yf)/total
            result=(2*(A*D-B*C)-A+D)/(2*(B*C-A*D)+A-D+1)
            self.assertAlmostEqual(abs(result-(k1+k3)/(ye+yf)),0,places=11)
    def test_passive_two_port_gives_no_return(self):
        ye,yf=2.,3.;A=-yf/(ye+yf);B=ye*yf/(ye+yf);C=1/(ye+yf);D=yf/(ye+yf)
        self.assertAlmostEqual((2*(A*D-B*C)-A+D)/(2*(B*C-A*D)+A-D+1),0)
    def test_no_source_candidate_mutation(self):
        p=HERE/'candidate_06.spice'; original=HERE.parent/'dynamic_20260911/candidate_06.spice'
        self.assertEqual(p.read_bytes(),original.read_bytes())
        s=instrument(p.read_text());self.assertIn('ITESTD I_SUMNEG I_SUMPOS dc 0 ac {DI}',s)
        self.assertEqual(s.count('VTESTNCM NCM_GATE NCM dc 0'),1)
    def test_evidence_hashes_and_scope(self):
        for run in (HERE/'runs').iterdir():
            if not (run/'manifest.json').exists():continue
            m=json.loads((run/'manifest.json').read_text())
            for name,x in m['files'].items():
                self.assertEqual(hashlib.sha256((run/name).read_bytes()).hexdigest(),x['sha256'])
            r=json.loads((run/'summary.json').read_text())
            self.assertFalse(r['formal_stability_gate_pass']);self.assertFalse(r['complete_frontend_qualified'])

class MultiportChecks(unittest.TestCase):
    def test_reconstructed_admittance_from_nodal_system(self):
        from run_multiport import reconstruct
        rng=np.random.default_rng(130)
        # Independent complex admittance network, including non-diagonal coupling.
        yee=np.diag([3.,4.,5.,6.])+rng.normal(size=(4,4))*.02j
        yff=np.diag([7.,8.,9.,10.])+rng.normal(size=(4,4))*.03j
        yef=rng.normal(size=(4,4))*.4+1j*rng.normal(size=(4,4))*.2
        yfe=rng.normal(size=(4,4))*.3+1j*rng.normal(size=(4,4))*.1
        physical=yee+yff+yef+yfe
        C=np.linalg.inv(physical);D=C@(yef+yff);A=-(yfe+yff)@C;B=yff-(yfe+yff)@D
        K,base,cross,F=reconstruct(A,B,C,D)
        np.testing.assert_allclose(K,physical,atol=1e-12)
        np.testing.assert_allclose(base,yee+yff,atol=1e-12)
        np.testing.assert_allclose(cross,yef+yfe,atol=1e-12)
        self.assertAlmostEqual(abs(F-np.linalg.det(physical)/np.linalg.det(yee+yff)),0,places=12)

class NoiseAudit(unittest.TestCase):
    def test_density_integral_matches_native_integrated_noise(self):
        import re
        count=0
        for run in (HERE/'runs').iterdir():
            p=run/'summary.json'
            if not p.exists():continue
            j=json.loads(p.read_text())
            if j['status']!='STATIC_NOISE_DIAGNOSTIC_COMPLETE':continue
            text=(run/'noise_integrated.raw').read_text()
            native=float(re.search(r'Values:\s*0\s+(\S+)',text)[1])
            integrated=j['output_rms_v']['1000000000']
            self.assertLess(abs(integrated/native-1),.001)
            count+=1
        self.assertEqual(count,6)

if __name__=='__main__':unittest.main()
