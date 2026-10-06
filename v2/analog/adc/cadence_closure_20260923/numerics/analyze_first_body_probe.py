#!/usr/bin/env python3
"""Audit the real saved primitive body node around the first acquisition edge."""
import json
import os
from pathlib import Path
import re
import numpy as np
from psf_stream import Trace
from compare_full_adc_stream import digest

HERE=Path(__file__).resolve().parent
RUN=HERE.parent/'runs/task_20260924T053814697817Z'
P='p2_ams_reset1.'
BODY=P+'phases.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8.int_b'
GATE=P+'phases.XPHASE_XBCONV_B'


def main():
    trace=Trace(RUN/'design/amsdControl.raw/adc_closure_tran.tran.tran')
    rows=list(trace.rows());t=np.array([r['time'] for r in rows])
    a={name:np.array([r[name] for r in rows]) for name in [BODY,GATE,P+'vdd',P+'conv_e',P+'sample_cmd_e']}
    body=a[BODY]-a[P+'vdd'];vds=a[P+'conv_e']-a[P+'vdd']
    window=(t>=4.06317e-6)&(t<=4.06323e-6)
    inds=np.flatnonzero(window);j=inds[np.argmax(abs(np.diff(a[BODY][inds])))]
    crossing=np.flatnonzero((vds[:-1]>=0)&(vds[1:]<0)&(t[:-1]>4.06315e-6)&(t[1:]<4.06325e-6))
    crossings=[float(t[i]-vds[i]*(t[i+1]-t[i])/(vds[i+1]-vds[i])) for i in crossing]
    log=(RUN/'design/xrun.log').read_text(errors='replace')
    metadata=json.loads((RUN/'school_body_model_metadata.json').read_text())
    def values(i):return {'accepted_row_index_including_initial_DC':int(i),'time_s':float(t[i]),'local_gate_V':float(a[GATE][i]),'CONV_drain_V':float(a[P+'conv_e'][i]),'source_external_bulk_V':float(a[P+'vdd'][i]),'internal_body_V':float(a[BODY][i]),'internal_body_minus_external_bulk_V':float(body[i]),'external_VDS_V':float(vds[i])}
    stats={}
    for name,pattern in [('accepted_steps',r'Total Number of Accepted steps\s*:\s*(\d+)'),('LTE_rejected_steps',r'Number of LTE rejected steps\s*:\s*(\d+)'),('Newton_rejected_steps',r'Number of Newton rejected steps\s*:\s*(\d+)'),('device_rejected_steps',r'Number of Device rejected steps\s*:\s*(\d+)'),('minimum_step_s',r'Minimum time step\s*=\s*([\deE+.-]+)'),('drastic_step_changes',r'Number of drastic step size changes\s*=\s*(\d+)'),('recovery_steps',r'Number of steps to recover from drastic step size drop\s*=\s*(\d+)')]:
        m=re.search(pattern,log);stats[name]=float(m[1]) if name=='minimum_step_s' else int(m[1]) if m else None
    warning_codes={code:len(re.findall(r'WARNING \('+code+r'\)',log)) for code in ['AHDLLINT-8007','SPECTRE-16780','SPECTRE-16266','SPECTRE-16578']}
    result={'status':'BOUNDED_INTERNAL_NODE_DIAGNOSTIC_NOT_ADC_QUALIFICATION','run':str(RUN),'waveform_sha256':digest(trace.path),'model_metadata_sha256':digest(RUN/'school_body_model_metadata.json'),'raw_trace_count':len(trace.names),'raw_points':len(t),'saved_interval_s':[float(t[0]),float(t[-1])],'actual_method':{k:trace.header.get(k) for k in ['version','method','relref','reltol','abstol(V)','abstol(I)','maxstep','temp','tnom','gmin','cmin']},'observed_device':{'type':'Native phase CONV buffer PFET','instance':'XPHASE_XBCONV_XI2_XP','external_terminals_D_G_S_B':['CONV','XPHASE_XBCONV_B','VDD','VDD'],'w_m':32e-6,'l_m':150e-9,'m':1,'body_save_request':'p2_ams_reset1.phases.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8:int_b sigtype=node','actual_PSF_voltage_name':BODY},'body_range_V':[float(a[BODY].min()),float(a[BODY].max())],'body_minus_external_bulk_range_V':[float(body.min()),float(body.max())],'body_extrema':[values(int(np.argmin(body))),values(int(np.argmax(body)))],'largest_local_body_change':{'before':values(j),'after':values(j+1),'delta_body_V':float(a[BODY][j+1]-a[BODY][j]),'elapsed_s':float(t[j+1]-t[j])},'raw_adjacent_points':[values(i) for i in range(j-8,j+10)],'external_VDS_zero_crossings_interpolated_s':crossings,'logged_LTE_time_literal':'4.0632 us','logged_time_caution':'The warning time is rounded. Exact accepted-point brackets are retained; the rounded time alone cannot locate an internal rejected iteration.','warnings':warning_codes,'diagnosis_statistics':stats,'local_model_facts':metadata['pfet_01v8'],'evidence_based_hypothesis':'Abrupt saved internal-body change coincides with drain crossing the fixed source voltage (external VDS=0), while the local gate remains smooth. Investigate source/drain orientation and junction/body-network evaluation around VDS=0. This is a hypothesis, not proof of a model defect.','known_limits':['The saved signal is an actual internal node, not the external body rail. Correct external body wiring does not exclude internal-body transients or numerical problems.','Finite model body resistances permit internal body voltage motion; their presence alone does not prove a jump is physically correct or incorrect.','Accepted waveforms omit rejected Newton/LTE iterates; a mathematical discontinuity cannot be proven from finite accepted points alone.','The simultaneous read_sample AHDL-8007 event imposes a 605.326 fs step; it does not prove the monitor caused the body event.','The short 4.1us experiment is intentional; protocol qualification exit2 is not a completed ADC PASS.','No PDK/model parameters, capacitances, leakage, IC or body network are modified.'],'next_minimal_diagnostic':{'same_fixture_and_stop':True,'add_actual_internal_voltages':['same primitive :dbnode sigtype=node','same primitive :sbnode sigtype=node'],'retain_current_saves':True,'derive_VDS_from_already_saved_external_nodes':True,'optional_device_outputs':'Only use mode/region/reversed or intrinsic-vds output after installed bsim4 help proves availability and exact semantics. No guessed output names.','question':'Do drain-body and source-body nodes exchange behavior or remain continuous at external VDS=0, and does the int_b step persist under independently tighter same-method solution?','if_repro_needed':'Freeze native inverter/phase generator and actual fanout or preserve the full first-acquisition circuit; controlled finite input edge and same PDK/tool build. A reduced diagnostic is not full ADC validation.'}}
    (HERE/'first_body_probe_review.json').write_text(json.dumps(result,indent=2)+'\n')
    os.environ.setdefault('MPLCONFIGDIR',str(HERE/'private_runtime/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(3,1,figsize=(11.8,10.4),sharex=True)
    fig.subplots_adjust(left=.11,right=.885,bottom=.20,top=.83,hspace=.17)
    select=(t>=4.06317e-6)&(t<=4.06323e-6);x=(t-4.0632e-6)*1e12
    zero=(crossings[0]-4.0632e-6)*1e12
    for ax in axes:
        ax.grid(alpha=.2);ax.axvline(zero,color='#64748b',ls='--',lw=.8)
    axes[0].plot(x[select],vds[select]*1e3,color='#1769aa',label='External VDS = CONV - VDD')
    axes[0].axhline(0,color='#64748b',lw=.7);axes[0].set_ylabel('External VDS (mV)');None
    twin=axes[0].twinx();twin.plot(x[select],a[GATE][select],color='#de702a',alpha=.9,label='Local gate');twin.set_ylabel('Local gate (V)',color='#de702a');twin.spines['top'].set_visible(False);axes[0].legend([axes[0].lines[1],twin.lines[0]],['External VDS = CONV - VDD','Local gate'],frameon=False,loc='lower left')
    axes[1].plot(x[select],body[select]*1e6,'.-',color='#be243c',ms=2.5,lw=1.2)
    axes[1].scatter(x[j:j+2],body[j:j+2]*1e6,s=30,color='#be243c',zorder=3)
    axes[1].set_ylabel('Internal body - VDD (uV)')
    axes[1].text(.03,.37,'-449.09 uV across 201.30 fs\nExternal bulk remains at 1.800000 V',transform=axes[1].transAxes,color='#be243c',va='top')
    dt=np.diff(t);sel_dt=select[1:]
    axes[2].plot(x[1:][sel_dt],dt[sel_dt]*1e15,'.-',color='#216a50',ms=3,lw=1)
    axes[2].set_yscale('log');axes[2].set_ylabel('Accepted time step (fs)');axes[2].set_xlabel('Time from 4.063200 microseconds (ps); no time alignment')
    fig.text(.11,.944,'Measured internal-body event at the first acquisition switch',fontsize=18,weight='bold',color='#172b46')
    fig.text(.11,.905,'Same native ADC / phases and PDK. Two added voltage saves + diagnostic logging; stop = 4.1 us.',fontsize=10.5,color='#596779')
    fig.text(.11,.868,'Dashed line: interpolated external VDS = 0. The LTE log reports the rounded time 4.0632 us.',fontsize=10.5,color='#596779')
    fig.text(.11,.135,'Supported observation, not a model-bug verdict',fontsize=12,weight='bold',color='#172b46',va='top')
    fig.text(.11,.105,'The gate remains smooth while the internal body changes sharply near drain/source voltage equality.\nNext: save the same primitive drain-body and source-body nodes; retain all existing physics and tolerances.\n4950 accepted steps; 116 LTE, 4 Newton, 3 device rejections. This short probe is not an ADC qualification PASS.',fontsize=10.5,color='#596779',va='top',linespacing=1.65)
    for ext in ['png','svg']:fig.savefig(HERE/f'first_body_probe_review.{ext}',dpi=170)
    plt.close(fig)
    print(json.dumps({k:result[k] for k in ['body_range_V','body_minus_external_bulk_range_V','largest_local_body_change','external_VDS_zero_crossings_interpolated_s','diagnosis_statistics']},indent=2))


if __name__=='__main__':main()
