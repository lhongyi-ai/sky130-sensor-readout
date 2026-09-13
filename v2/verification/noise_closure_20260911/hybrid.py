#!/usr/bin/env python3
"""Finite-band, frozen-bias LTI sampled-noise planning model, NOT ADC SNDR.

Preserves ngspice's actual BSIM4v5 output PSD; no VACASK correction factor.
Folds continuous one-sided PSD power into ideal instantaneous sampling bins.
Out-of-table noise is UNKNOWN, never asserted physically zero. The returned
power is explicitly the contribution from the measured band only.
"""
from __future__ import annotations
import numpy as np


class PSDTable:
    """Positive piecewise-power-law PSD with an analytic cumulative integral."""

    def __init__(self, frequency, psd):
        self.f=np.asarray(frequency,dtype=float)
        self.p=np.asarray(psd,dtype=float)
        if (self.f.ndim!=1 or self.p.shape!=self.f.shape or len(self.f)<2
                or not np.isfinite(self.f).all() or not np.isfinite(self.p).all()
                or np.any(self.f<=0) or np.any(np.diff(self.f)<=0) or np.any(self.p<=0)):
            raise ValueError('Need finite, strictly increasing positive frequencies and positive PSD')
        self.exponent=np.log(self.p[1:]/self.p[:-1])/np.log(self.f[1:]/self.f[:-1])
        self.cumulative=np.r_[0.,np.cumsum(self._segment(np.arange(len(self.f)-1),self.f[1:]))]

    def _segment(self,index,end):
        q=self.exponent[index]+1.
        logratio=np.log(np.asarray(end)/self.f[index])
        # expm1(q*x)/q has limit x for exponent=-1 (flicker noise).
        factor=np.empty_like(logratio,dtype=float)
        mask=np.abs(q)<1e-10
        factor[mask]=logratio[mask]
        factor[~mask]=np.expm1(q[~mask]*logratio[~mask])/q[~mask]
        return self.p[index]*self.f[index]*factor

    def cdf(self,value):
        value=np.asarray(value,dtype=float)
        shape=value.shape
        clipped=np.clip(value.ravel(),self.f[0],self.f[-1])
        index=np.clip(np.searchsorted(self.f,clipped,side='right')-1,0,len(self.f)-2)
        return (self.cumulative[index]+self._segment(index,clipped)).reshape(shape)

    def integral(self,lo,hi):
        lo,hi=np.broadcast_arrays(np.asarray(lo,dtype=float),np.asarray(hi,dtype=float))
        if np.any(hi<lo):raise ValueError('Reversed integration interval')
        return np.maximum(0.,self.cdf(hi)-self.cdf(lo))

    def folded_bin_power(self,edges,fs):
        edges=np.asarray(edges,dtype=float)
        if (not np.isfinite(fs) or fs<=0 or edges.ndim!=1 or len(edges)<2
                or not np.isfinite(edges).all() or np.any(np.diff(edges)<=0)
                or edges[0]<0 or edges[-1]>fs/2):
            raise ValueError('Bin edges must increase within [0, fs/2]')
        lo,hi=edges[:-1],edges[1:]
        # One-sided continuous PSD. k=0 direct band, k>=1 both sides of k*fs.
        # This partitions positive analog frequency without factor-of-two errors.
        power=self.integral(lo,hi)
        for k in range(1,int(np.ceil(self.f[-1]/fs))+1):
            power+=self.integral(k*fs+lo,k*fs+hi)
            power+=self.integral(k*fs-hi,k*fs-lo)
        return power


def fft_bin_edges(n,fs):
    if not isinstance(n,int) or n<4 or n%2:raise ValueError('Even n >= 4 required')
    centers=np.fft.rfftfreq(n,1/fs)
    return np.r_[0.,(centers[1:]+centers[:-1])/2,fs/2]


def gaussian_samples(bin_power,n,seed):
    """Periodic finite-record stationary Gaussian model, not process mismatch.

    Each FFT bin receives its integrated known-band variance. No ad-hoc white
    input is added to a transistor circuit. DC is a random record mean; use mean
    square, not demeaned variance, when checking total expected bin power.
    """
    power=np.asarray(bin_power,dtype=float)
    if (n<4 or n%2 or power.shape!=(n//2+1,) or not np.isfinite(power).all()
            or np.any(power<0)):
        raise ValueError('Invalid nonnegative real-FFT bin powers')
    rng=np.random.default_rng(seed)
    spectrum=(rng.normal(size=len(power))+1j*rng.normal(size=len(power)))*n*np.sqrt(power/4.)
    spectrum[0]=rng.normal()*n*np.sqrt(power[0])
    spectrum[-1]=rng.normal()*n*np.sqrt(power[-1])
    return np.fft.irfft(spectrum,n=n)


def qualification_gate(evidence):
    """Noise qualification cannot be obtained from this planning model alone."""
    required=['same_pdk_model_version','intrinsic_time_varying_device_noise',
              'switching_sampling_and_comparator_included','bandwidth_step_convergence',
              'representative_bias_and_pvt_coverage','top_level_noise_aware_dynamic_validation']
    return bool(all(evidence.get(key) is True for key in required))
