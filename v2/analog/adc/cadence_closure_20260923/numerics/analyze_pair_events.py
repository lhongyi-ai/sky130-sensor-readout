#!/usr/bin/env python3
"""Attribute strict-pair differences without altering the complete-waveform gate."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from psf_stream import Trace
from compare_full_adc_stream import CHANNELS,LIMIT,PREFIX,digest


def load(design):
    needed={n for ns in CHANNELS.values() for n in ns}|{PREFIX+n for n in ["conv_e","acq_e","top_e","topb_e","sample_cmd_e","eval_e","q_e","qb_e"]}
    path=design/"amsdControl.raw/adc_closure_tran.tran.tran"
    trace=Trace(path,needed);rows=list(trace.rows())
    return np.array([r['time'] for r in rows]),{n:np.array([r[n] for r in rows]) for n in needed},digest(path)


def analyze(baseline,strict):
    ta,aa,ha=load(baseline);tb,ab,hb=load(strict)
    end=min(ta[-1],tb[-1]);grid=np.union1d(ta[ta<=end],tb[tb<=end])
    delta={};signals={}
    for k,ns in CHANNELS.items():
        va=sum((1 if i==0 else -1)*np.interp(grid,ta,aa[n]) for i,n in enumerate(ns))
        vb=sum((1 if i==0 else -1)*np.interp(grid,tb,ab[n]) for i,n in enumerate(ns))
        delta[k]=vb-va;signals[k]=(va,vb)
    y=delta['CDAC_TP_minus_TN'];mask=abs(y)>LIMIT
    starts=np.flatnonzero(mask & ~np.r_[False,mask[:-1]])
    ends=np.flatnonzero(mask & ~np.r_[mask[1:],False])
    episodes=[]
    for left,right in zip(starts,ends):
        peak=left+np.argmax(abs(y[left:right+1]))
        episodes.append({'first_exceed_point_s':float(grid[left]),'last_exceed_point_s':float(grid[right]),'preceding_point_s':float(grid[max(0,left-1)]),'following_point_s':float(grid[min(len(grid)-1,right+1)]),'peak_time_s':float(grid[peak]),'peak_abs_V':float(abs(y[peak])),'accepted_point_span_s':float(grid[right]-grid[left])})
    maxidx=int(np.argmax(abs(y)));worst_t=float(grid[maxidx]);worst_episode=next(e for e in episodes if e['first_exceed_point_s']<=worst_t<=e['last_exceed_point_s'])
    post=(grid>=worst_t+10e-9)&(grid<=worst_t+100e-9)
    windows=[]
    # Both acquisition-to-conversion transitions and all true 24 decisions.
    decisions=list(csv.DictReader((baseline/'decisions.csv').open()))
    for d in decisions:
        capture=float(d['time_ns'])*1e-9
        for kind,at in [('pre_EVAL',capture-312.5e-9-1e-9),('pre_capture',capture-1e-9)]:
            if at>end:continue
            vals={k:float(np.interp(at,grid,z)) for k,z in delta.items()}
            windows.append({'frame':int(d['frame']),'decision':int(d['decision']),'kind':kind,'time_s':at,'strict_minus_baseline_V':vals,'all_physical_channels_le_0_05_LSB':all(abs(v)<=LIMIT for v in vals.values())})
    crossings=[]
    for label,t,a in [('baseline',ta,aa),('strict',tb,ab)]:
        for short in ['conv_e','acq_e','top_e','topb_e','sample_cmd_e']:
            v=a[PREFIX+short]
            for rise in [False,True]:
                cond=(v[:-1]<.9)&(v[1:]>=.9) if rise else (v[:-1]>.9)&(v[1:]<=.9)
                ix=np.flatnonzero(cond & (t[:-1]>=worst_t-40e-9)&(t[1:]<=worst_t+40e-9))
                for j in ix:
                    at=t[j]+(.9-v[j])*(t[j+1]-t[j])/(v[j+1]-v[j])
                    crossings.append({'run':label,'signal':short,'direction':'rise' if rise else 'fall','time_s':float(at)})
    return {'status':'PARTIAL_PAIR_DIAGNOSTIC_FULL_GATE_REMAINS_FAIL','raw_sha256':{'baseline':ha,'strict':hb},'shared_interval_s':[0,float(end)],'limit_V':LIMIT,'worst_CDAC_episode':worst_episode,'episode_definition':'Contiguous union sample points exceeding limit; neighboring brackets retained, no exclusion/alignment or accuracy pass based on recovery. Subthreshold holes split episodes.','all_CDAC_exceedance_episodes':episodes,'CDAC_peak_after_10ns_through_100ns_V':float(abs(y[post]).max()),'CDAC_delta_at_peak_plus_ns':{str(ns):float(np.interp(worst_t+ns*1e-9,grid,y)) for ns in [1,2,5,10,20,50,100]},'scheduled_decision_observations':windows,'decision_max_abs_V':{kind:{k:max(abs(w['strict_minus_baseline_V'][k]) for w in windows if w['kind']==kind) for k in CHANNELS} for kind in ['pre_EVAL','pre_capture']},'phase_halfrail_crossings_near_worst':crossings,'limitations':['Interpolation at scheduled decisions is supplemental; the original all-time physical gate and all failed switching edges remain unchanged.','Observed edge displacement is descriptive, not proof that all differences are harmless timing shifts.','Both model recovery warnings and incomplete strict run prevent qualification.']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('strict',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=analyze(a.baseline,a.strict);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['worst_CDAC_episode','CDAC_peak_after_10ns_through_100ns_V','CDAC_delta_at_peak_plus_ns','decision_max_abs_V','phase_halfrail_crossings_near_worst']},indent=2))
