"""Numerical measurement helpers shared by current and historical evidence audits."""
import numpy as np

integrator=np.trapezoid if hasattr(np,'trapezoid') else np.trapz

def checked_data(path, stop=None):
    data=np.loadtxt(path,skiprows=1,ndmin=2)
    if len(data)<2 or not np.all(np.isfinite(data)):
        raise ValueError(f'Missing or nonfinite measurement data: {path}')
    if np.any(np.diff(data[:,0])<0):
        raise ValueError(f'Nonmonotone independent variable: {path}')
    if stop is not None and data[-1,0]<stop*(1-1e-7):
        raise ValueError(f'Incomplete measurement range: {path}, end={data[-1,0]}, required={stop}')
    return data

def interval_stats(time,values,start,end):
    if time[0]>start or time[-1]<end or end<=start:
        raise ValueError('Reference interval is not completely covered')
    inside=(time>start)&(time<end)
    t=np.r_[start,time[inside],end]
    v=np.r_[np.interp(start,time,values),values[inside],np.interp(end,time,values)]
    return float(integrator(v,t)/(end-start)),float(np.ptp(v))
