#!/usr/bin/env python3
"""Plot retained measured simulator traces; no synthetic or aligned waveforms."""
from pathlib import Path
import json
import os
HERE=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(HERE/'private_runtime/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from analyze_pair_events import load
from compare_full_adc_stream import PREFIX,LIMIT


def main():
    base=HERE.parent/'runs/task_20260924T050345927509Z/design'
    strict=HERE.parent/'runs/task_20260924T051121445887Z/design'
    ta,a,ha=load(base);tb,b,hb=load(strict)
    da=a[PREFIX+'adc.XADC_TP']-a[PREFIX+'adc.XADC_TN']
    db=b[PREFIX+'adc.XADC_TP']-b[PREFIX+'adc.XADC_TN']
    end=min(ta[-1],tb[-1]);grid=np.union1d(ta[ta<=end],tb[tb<=end])
    delta=np.interp(grid,tb,db)-np.interp(grid,ta,da)
    peak=int(np.argmax(abs(delta)));tp=float(grid[peak]);peak_mV=float(delta[peak]*1e3)
    review=json.loads((HERE/'full_adc_strict_partial_event_attribution.json').read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'axes.labelsize':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,2,figsize=(15.2,10.6))
    fig.subplots_adjust(left=.072,right=.965,bottom=.18,top=.81,hspace=.47,wspace=.27)
    fig.patch.set_facecolor('#f6f8fb')
    blue='#1769aa';orange='#d85d23';red='#be243c';green='#2a8060';grey='#596779'
    for ax in axes.flat:
        ax.set_facecolor('white');ax.grid(alpha=.16);ax.tick_params(colors=grey)
    anchor=16.586e-6
    ax=axes[0,0]
    for t,v,color,label in [(ta,da,blue,'Baseline'),(tb,db,orange,'10x tighter tolerances')]:
        ix=(t>=anchor+.1e-9)&(t<=anchor+.48e-9)
        ax.plot((t[ix]-anchor)*1e12,v[ix],color=color,lw=1.6,label=label)
    ax.set(title='A  Actual CDAC waveform at conversion switching',xlabel='Time from 16.586000 microseconds (ps)',ylabel='TP - TN (V)')
    ax.legend(frameon=False,loc='lower left',fontsize=10)
    ax.text(.03,.96,'Same absolute time axis in both runs\nCONV edge shift: about 1.49 ps',transform=ax.transAxes,va='top',fontsize=10,color=grey,bbox={'facecolor':'white','edgecolor':'none','alpha':.85})
    ax=axes[0,1];ix=(grid>=anchor+.1e-9)&(grid<=anchor+.48e-9)
    ax.plot((grid[ix]-anchor)*1e12,delta[ix]*1e3,color=red,lw=1.7)
    ax.axhline(0,color=grey,lw=.6)
    ax.scatter([(tp-anchor)*1e12],[peak_mV],color=red,s=25,zorder=3)
    ax.annotate(f'{peak_mV:.3f} mV maximum\n73.60 LSB waveform difference',xy=((tp-anchor)*1e12,peak_mV),xytext=(.46,.68),textcoords='axes fraction',fontsize=11,color=red,arrowprops={'arrowstyle':'-','color':red})
    ax.set(title='B  Difference retains the complete switching edge',xlabel='Time from 16.586000 microseconds (ps)',ylabel='Strict - baseline, TP - TN (mV)')
    ax.text(.025,.94,'Limit: 9.765625 microvolts\nFull-time FAIL retained',transform=ax.transAxes,va='top',fontsize=10,color=red)
    ax=axes[1,0];ix=(grid>=tp)&(grid<=tp+100e-9)
    ax.plot((grid[ix]-tp)*1e9,delta[ix]*1e6,color=red,lw=1.3)
    ax.axhspan(-LIMIT*1e6,LIMIT*1e6,color=green,alpha=.14,label='+/- 0.05 LSB = +/- 9.765625 microvolts')
    ax.axhline(LIMIT*1e6,color=green,lw=.8,ls='--');ax.axhline(-LIMIT*1e6,color=green,lw=.8,ls='--')
    ax.set_yscale('symlog',linthresh=1)
    ax.set(title='C  Recovery is not instantaneous',xlabel='Time after the same physical peak (ns)',ylabel='Strict - baseline (microvolts; symlog)')
    ax.legend(frameon=False,fontsize=9,loc='upper right')
    ax.text(.38,.72,'Intermittent excess lasts about 32.6 ns\nSettling later does not waive the full-time FAIL',transform=ax.transAxes,fontsize=10,color=grey)
    ax=axes[1,1]
    for kind,label,col,marker in [('pre_EVAL','1 ns before EVAL',blue,'o'),('pre_capture','1 ns before decision capture',orange,'s')]:
        rows=[r for r in review['scheduled_decision_observations'] if r['kind']==kind]
        x=[(r['frame']-1)*12+r['decision']+1 for r in rows]
        y=[r['strict_minus_baseline_V']['CDAC_TP_minus_TN']*1e12 for r in rows]
        ax.plot(x,y,color=col,marker=marker,ms=3,lw=1,label=label)
    ax.axvline(12.5,color=grey,ls='--',lw=.7)
    ax.set(title='D  Settled observation points agree very closely',xlabel='Actual SAR decision index (12 per frame)',ylabel='Strict - baseline, TP - TN (pV)',xticks=[1,6,12,13,18,24])
    ax.legend(frameon=False,fontsize=9,loc='upper left')
    ax.text(.54,.12,'Frame 2',transform=ax.transAxes,color=grey,fontsize=10)
    ax.text(.09,.12,'Frame 1',transform=ax.transAxes,color=grey,fontsize=10)
    fig.text(.072,.945,'ADC numerical check: full-time waveform gate FAILED',fontsize=21,weight='bold',color='#172b46')
    fig.text(.072,.907,'Real analog ADC + original RTL | identical circuit and stimulus | 10x tighter tolerances, 2 ns -> 1 ns maxstep',fontsize=11.5,color=grey)
    fig.text(.072,.872,'No edge deletion or time alignment. Two matching output codes do not prove numerical convergence.',fontsize=12,color=red)
    fig.text(.072,.128,'What this means',fontsize=12,weight='bold',color='#172b46',va='top')
    fig.text(.072,.103,'14.374 mV is an instantaneous difference between two simulated CDAC waveforms, NOT an ADC conversion error.\nThe recorded codes remain 5 and 4090. Strict run timed out before completing the reset-abort checks; LTE warnings remain.',fontsize=10.5,color=grey,linespacing=1.65,va='top')
    fig.text(.072,.033,'Plots A-C are diagnostic zooms only. The audit retains every accepted point across the full shared record and all 399 exceedance episodes.',fontsize=9,color=grey)
    for suffix in ['png','svg']:fig.savefig(HERE/f'full_adc_numerical_failure.{suffix}',dpi=170,facecolor=fig.get_facecolor())
    plt.close(fig)
    (HERE/'full_adc_numerical_failure_figure_metadata.json').write_text(json.dumps({'baseline_sha256':ha,'strict_sha256':hb,'physical_peak_time_s':tp,'peak_difference_V':float(delta[peak]),'plots_use':'Raw accepted-time waveforms; differences on complete union using linear interpolation, no alignment; A-C show declared diagnostic zooms only.','acceptance':'FAIL remains, no simulation synthesized or modified.','source_review':'full_adc_strict_partial_event_attribution.json'},indent=2)+'\n')


if __name__=='__main__':main()
