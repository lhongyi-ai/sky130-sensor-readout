import unittest
import numpy as np
from hybrid import PSDTable, fft_bin_edges, gaussian_samples, qualification_gate


class FiniteBandSamplingTest(unittest.TestCase):
    def test_constant_integral(self):
        t=PSDTable([1,10,100],[2,2,2])
        self.assertAlmostEqual(float(t.integral(1,100)),198)

    def test_flicker_integral(self):
        t=PSDTable([1,10,100],[3,.3,.03])
        self.assertAlmostEqual(float(t.integral(1,100)),3*np.log(100))

    def test_unknown_band_not_extrapolated(self):
        t=PSDTable([10,100],[1,1])
        self.assertAlmostEqual(float(t.integral(0,1000)),90)
        self.assertAlmostEqual(float(t.integral(0,9)),0)

    def test_invalid_inputs(self):
        for f,p in [([0,1],[1,1]),([1,1],[1,1]),([1,2],[1,0]),([1,2],[1,np.nan])]:
            with self.assertRaises(ValueError):PSDTable(f,p)

    def test_alias_power_conservation(self):
        t=PSDTable(np.geomspace(1,1e7,1001),1/np.geomspace(1,1e7,1001))
        bins=t.folded_bin_power(fft_bin_edges(256,100000.),100000.)
        self.assertAlmostEqual(float(np.sum(bins)/np.log(1e7)),1.,places=12)

    def test_alias_fold_at_45khz(self):
        # Narrow power near 145kHz must fold to 45kHz at 100kS/s.
        t=PSDTable([144900,145100],[1,1])
        power=t.folded_bin_power([0,44000,46000,50000],100000)
        np.testing.assert_allclose(power,[0,200,0])

    def test_negative_side_alias(self):
        # 95kHz folds to 5kHz, checking the k*fs-f branch.
        t=PSDTable([94900,95100],[1,1])
        np.testing.assert_allclose(t.folded_bin_power([0,4900,5100,50000],100000),[0,200,0])

    def test_no_factor_two_for_baseband(self):
        t=PSDTable([100,200],[1,1])
        self.assertAlmostEqual(float(t.folded_bin_power([0,500],1000)[0]),100)

    def test_rc_fold_against_exact_sampled_covariance_psd(self):
        # Exact stationary RC covariance: kT/C * exp(-abs(lag)*Ts/(RC)).
        fs=100000.;tau=1e-5;ktc=4.1440179735e-12
        f=np.geomspace(.001,1e9,20001)
        p=4*ktc*tau/(1+(2*np.pi*f*tau)**2)
        table=PSDTable(f,p)
        # At non-edge bins, integrated-power/bin-width approaches analytic PSD.
        edges=np.array([4999.,5001.])
        folded=float(table.folded_bin_power(edges,fs)[0]/2.)
        a=np.exp(-1/(fs*tau))
        exact=2*ktc/fs*(1-a*a)/(1+a*a-2*a*np.cos(2*np.pi*5000/fs))
        self.assertLess(abs(folded/exact-1),2e-5)

    def test_seed_reproducibility(self):
        p=np.ones(513)*1e-12
        a=gaussian_samples(p,1024,11)
        np.testing.assert_array_equal(a,gaussian_samples(p,1024,11))
        self.assertFalse(np.array_equal(a,gaussian_samples(p,1024,29)))

    def test_expected_realization_power(self):
        p=np.ones(513)*1e-12
        powers=[np.mean(gaussian_samples(p,1024,seed)**2) for seed in range(200)]
        self.assertLess(abs(np.mean(powers)/np.sum(p)-1),.02)

    def test_dc_bin_counts_record_mean(self):
        p=np.zeros(513);p[0]=1
        v=gaussian_samples(p,1024,11)
        self.assertEqual(float(np.ptp(v)),0.)
        self.assertGreater(float(np.mean(v*v)),0.)

    def test_reject_missing_time_varying_physics(self):
        self.assertFalse(qualification_gate({'same_pdk_model_version':True}))

    def test_reject_model_only_claim(self):
        self.assertFalse(qualification_gate({'planning_method_pass':True,'noise_realizations':200,'sndr_db':80}))

    def test_unknown_or_truthy_evidence_is_not_verified(self):
        self.assertFalse(qualification_gate({key:'yes' for key in [
            'same_pdk_model_version','intrinsic_time_varying_device_noise',
            'switching_sampling_and_comparator_included','bandwidth_step_convergence',
            'representative_bias_and_pvt_coverage','top_level_noise_aware_dynamic_validation']}))


if __name__=='__main__':unittest.main()
