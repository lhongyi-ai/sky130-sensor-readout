#!/usr/bin/env python3
"""Verify immutable raw evidence, then make a separately timestamped review."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def put(p,x): Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def verify(p):
    manifest=load(p/'manifest.json')
    for name,h in manifest.items():
        if sha(p/name)!=h: raise ValueError('Evidence hash mismatch: '+str(p/name))
    return len(manifest)
def curve(p,name):
    with (p/(name+'.csv')).open() as f: a=list(csv.DictReader(f))
    x=np.array([float(z['x']) for z in a]); y=np.array([complex(float(z['real']),float(z['imag'])) for z in a])
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)) or not np.all(np.diff(x)>0): raise ValueError('Invalid curve')
    return x,y
def getac(p):
    f,o=curve(p,'VOUT'); fp,ip=curve(p,'VINP'); fn,inn=curve(p,'VINN')
    if not np.array_equal(f,fp) or not np.array_equal(f,fn): raise ValueError('Axis mismatch')
    if np.any(abs(ip-inn)==0): raise ValueError('No differential stimulus')
    return f,o/(ip-inn)
def at1k(f,z): return float(np.interp(3,np.log10(f),20*np.log10(abs(z))))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--campaign',type=Path,required=True); ap.add_argument('--reference',type=Path,required=True); args=ap.parse_args()
    campaign=args.campaign.resolve(); reference=args.reference.resolve()
    verified=verify(campaign)+verify(reference)
    execution=load(campaign/'execution.json')
    if execution['status']!='LOCAL_EXECUTION_COMPLETE' or execution['extra_jobs']!=32: raise ValueError('32-job campaign incomplete')
    out=HERE/'reviews'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); out.mkdir(parents=True)
    jobs={p.parent.name:load(p) for p in campaign.glob('*/job.json')}
    metrics={p.parent.name:load(p) for p in campaign.glob('*/metrics.json')}
    statuses={p.parent.name:load(p) for p in campaign.glob('*/status.json')}
    rows=[]
    for name,j in jobs.items():
        if j['group']!='extra': continue
        rows.append(dict(job_id=name,analysis=j['analysis'],CL_pF=j['params']['CL']*1e12,VCM_V=j['params']['VCM'],execution_status=statuses[name]['execution_status'],legacy_automatic_status=metrics[name]['status'],gain_dB=metrics[name].get('gain_dB'),pm_deg=metrics[name].get('pm_deg'),worst_settling_us=metrics[name].get('worst_settling_us'),device_saturation_pass=metrics[name]['all_devices_saturated'],diagnostic_count=len(statuses[name]['diagnostics'])))
    with (out/'jobs32.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    school=ROOT/'cadence/project1/reports/basic_20260913T023544Z_5cc09eef/received/runs/P01_ac/20260913T015526Z_53d3402e'
    sm=load(school/'metrics.json'); lm=metrics['support_nominal_ac']
    baseline={k:dict(local=lm[k],school=sm[k],difference=lm[k]-sm[k]) for k in ['gain_dB','power_uW','ac_unity_frequency_MHz']}
    nominal_match=all(abs(v['difference']) <= (0.001 if k=='gain_dB' else abs(v['school'])*0.001) for k,v in baseline.items())
    if not nominal_match: raise ValueError('Baseline mismatch requires review')
    f,ad=getac(reference); refm=load(reference/'metrics.json')
    rejection={}; responses={}
    for name,metric,stim,limit in [('nom_cm','CMRR','VINP',55),('nom_psrrp','PSRR+','VDD',45),('nom_psrrm','PSRR-','VSS',45)]:
        # AC excitation differs; the DC operating point must agree.
        diffs={n:abs(metrics[name]['dc_nodes'][n]-refm['dc_nodes'][n]) for n in ['VDD','VSS','VINP','VOUT','VBP']}
        if max(diffs.values())>1e-6: raise ValueError('Rejection reference DC bias differs')
        fy,vo=curve(campaign/name,'VOUT'); fs,s=curve(campaign/name,stim)
        if not np.array_equal(f,fy) or not np.array_equal(f,fs) or np.any(abs(s)==0): raise ValueError('Rejection axes/stimulus mismatch')
        z=ad/(vo/s); responses[metric]=20*np.log10(abs(z)); value=at1k(f,z)
        rejection[metric]=dict(value_1k_dB=value,limit_dB=limit,status='PASS' if value>=limit else 'FAIL',max_dc_bias_difference_V=max(diffs.values()))
    ni,noise=curve(campaign/'nom_noise','in')
    if abs(ni[0]-10)>1e-8 or abs(ni[-1]-1e6)>1e-2 or len(ni)!=501 or np.any(noise.real<0) or np.any(noise.imag): raise ValueError('Noise band/data incomplete')
    noise_report=dict(density_1k_nV_sqrtHz=float(np.interp(3,np.log10(ni),noise.real))*1e9,rms_10Hz_1MHz_uV=math.sqrt(float(np.trapezoid(noise.real**2,ni) if hasattr(np,'trapezoid') else np.trapz(noise.real**2,ni)))*1e6,status='REPORTED_NO_LIMIT',integration='sqrt(trapezoid(amplitude_density**2,frequency)); ngspice default unset sqrnoise',warnings=statuses['nom_noise']['diagnostics'])
    icmr=[]; g0=metrics['icmr_09']['gain_dB']
    for n in range(19):
        m=metrics[f'icmr_{n:02d}']; v=jobs[f'icmr_{n:02d}']['params']['VCM']; delta=m['gain_dB']-g0
        valid=delta>=-3 and m['all_devices_saturated'] and 0<m['dc_nodes']['VOUT']<1.8
        icmr.append(dict(VCM_V=v,gain_dB=m['gain_dB'],gain_delta_dB=delta,min_saturation_margin_V=m['min_saturation_margin_V'],valid=bool(valid),old_absolute_gain_status=m['status']))
    low=high=9
    if not icmr[9]['valid']: raise ValueError('ICMR nominal invalid')
    while low>0 and icmr[low-1]['valid']: low-=1
    while high<18 and icmr[high+1]['valid']: high+=1
    icmr_report=dict(grid_step_V=0.1,sampled_interval_V=[icmr[low]['VCM_V'],icmr[high]['VCM_V']],status='PASS' if low<=8 and high>=13 else 'FAIL',definition='Contiguous sampled interval containing 0.9 V, gain loss <=3 dB, all intended MOS saturation and output inside supply rails; endpoints are grid-limited, not a continuous boundary certificate.',points=icmr)
    loads=[]
    for c in [1,2,10,20]:
        loop=metrics[f'load_{c}p_loop']; step=metrics[f'load_{c}p_step']
        loads.append(dict(CL_pF=c,pm_deg=loop['pm_deg'],ugb_MHz=loop['ugb_MHz'],loop_status=loop['status'],step_status=step['status'],settling_ns=step['worst_settling_us']*1e3 if step['worst_settling_us'] is not None else None,sr_pos_V_us=step['sr_pos_V_per_us'],sr_neg_V_us=step['sr_neg_V_per_us'],scope='required nominal load' if c in [1,2] else 'extended characterization; outside original 1/2/5pF mandatory load matrix'))
    x,y=curve(campaign/'nom_swing','VOUT'); _,vin=curve(campaign/'nom_swing','VINP')
    tracking=abs(y.real-vin.real)<=.01
    follower=dict(sampled_tracking_points_V=x[tracking].tolist(),max_abs_error_V=float(max(abs(y.real-vin.real))),formal_output_swing_status='NOT_QUALIFIED_BY_THIS_BENCH',reason='This school extra job is a DC follower sweep; it moves input common-mode, has no sweep-point device OP or reverse sweep, and is not the frozen offset-inverting output-swing method.')
    fig,axs=plt.subplots(2,2,figsize=(11.5,7.5),constrained_layout=True)
    for c in [1,2,10,20]:
        fl,vo=curve(campaign/f'load_{c}p_loop','VOUT'); _,vn=curve(campaign/f'load_{c}p_loop','VINN')
        axs[0,0].semilogx(fl,20*np.log10(abs(-vo/vn)),label=f'{c} pF')
    axs[0,0].axhline(0,color='grey',lw=.8); axs[0,0].set(xlim=(1e3,1e9),ylim=(-80,70),title='Load return ratio',xlabel='Frequency (Hz)',ylabel='dB'); axs[0,0].legend()
    for label,z in responses.items(): axs[0,1].semilogx(f,z,label=label)
    axs[0,1].set(xlim=(10,1e8),title='Rejection with same-OP differential reference',xlabel='Frequency (Hz)',ylabel='dB'); axs[0,1].legend()
    axs[1,0].plot([p['VCM_V'] for p in icmr],[p['gain_delta_dB'] for p in icmr],'o-'); axs[1,0].axhline(-3,color='red',ls='--'); axs[1,0].axvspan(.8,1.3,color='green',alpha=.08); axs[1,0].set(title='ICMR gain relative to VCM = 0.9 V',xlabel='Input common mode (V)',ylabel='Gain change (dB)')
    axs[1,1].loglog(ni,noise.real*1e9); axs[1,1].set(title='Static input noise; model warnings retained',xlabel='Frequency (Hz)',ylabel='nV / sqrt(Hz)')
    for ax in axs.flat: ax.grid(True,alpha=.2)
    fig.savefig(out/'characterization.png',dpi=170); plt.close(fig)
    report=dict(status='LOCAL_32_JOB_CHARACTERIZATION_COMPLETE_WITH_FAILURES',cadence_extra_status='AWAITING_SCHOOL_RAW_RESULTS',campaign=str(campaign.relative_to(ROOT)),reference=str(reference.relative_to(ROOT)),evidence_files_verified=verified,core_sha256=statuses['support_nominal_ac']['core_sha256'],execution_jobs=33,extra_jobs=32,additional_same_op_reference_jobs=1,automatic_32_status_counts=dict(Counter(r['legacy_automatic_status'] for r in rows)),baseline_comparison=baseline,rejection=rejection,noise=noise_report,icmr=icmr_report,loads=loads,follower=follower,school_baseline_metrics_sha256=sha(school/'metrics.json'))
    put(out/'review.json',report)
    lines=['# 旧 OTA：32 项本地对应测试复现报告','',
        '**32/32 项本地 ngspice 对应测试全部实际执行并完成导出，性能存在失败。学校 Cadence 的 32 项仍需回传原始结果，不能据此记为已完成。**','',
        '使用学校已经导出的 13 个 MOS 尺寸和扩散几何，保持 3 pF / 2 kΩ 补偿、100 kΩ 负载和理想外部 10 µA 偏置。旧电路与历史结果均未修改。本次另跑一个标称差分核对，以及一个同偏置差分参考，共 34 次有效仿真。', '',
        '## 结果','',
        '| 项目 | 本地结果 | 判定 |','|---|---:|---|']
    for label,m in rejection.items(): lines.append(f'| {label} @ 1 kHz | {m["value_1k_dB"]:.4f} dB | {m["status"]}，门限 {m["limit_dB"]} dB |')
    lines += [f'| 输入共模范围 | 0.1 V 网格内 {icmr[low]["VCM_V"]:.1f}～{icmr[high]["VCM_V"]:.1f} V | {icmr_report["status"]}，未覆盖 1.3 V |',f'| 1 kHz 输入噪声 | {noise_report["density_1k_nV_sqrtHz"]:.3f} nV/√Hz | 仅报告，无硬门限 |',f'| 10 Hz～1 MHz 输入噪声 | {noise_report["rms_10Hz_1MHz_uV"]:.3f} µV RMS | 仅报告，保留模型警告 |','',
        '| 负载 | 相位裕度 | 最差建立时间 | 环路／阶跃 |','|---|---:|---:|---|']
    for l in loads: lines.append(f'| {l["CL_pF"]} pF | {l["pm_deg"]:.3f}° | {l["settling_ns"]:.3f} ns | {l["loop_status"]} / {l["step_status"]} |')
    lines += ['', '10/20 pF 是扩展表征，超出原规格要求的 1/2/5 pF 负载矩阵。它们的环路未达到 55°，即使阶跃最终建立，也不能以阶跃 PASS 覆盖相位裕度失败。', '',
        f'共模扫描的自动单项判据只检查绝对增益 ≥50 dB；ICMR 还必须相对 0.9 V 不下降超过 3 dB。因此 icmr_13 的自动状态为 {metrics["icmr_13"]["status"]}，但增益变化 {icmr[13]["gain_delta_dB"]:.3f} dB，不能计为 ICMR 通过。范围端点只有 0.1 V 网格精度，不声称找到了连续边界。', '',
        '直流跟随扫描已完整执行，但它同时移动输入共模，且缺少逐点工作区和反向扫描，不能替代冻结规格的独立输出摆幅验收。', '',
        '![表征曲线](characterization.png)', '', '## 复现一致性与已修正的本地检查问题', '',
        f'标称差分增益相对学校数据差 {baseline["gain_dB"]["difference"]:.9f} dB；功耗差 {baseline["power_uW"]["difference"]:.9f} µW。此处是名义电路与工具对照，不是新版前端指标。', '',
        '首次 smoke 的原始 BSIM PMOS 工作点使用类型归一化正值，而复用的学校分析器要求有符号 D−S / G−S 值，导致工作区假失败。该试验完整保留；正式运行只在导出适配中转换 PMOS id/vgs/vds/vdsat 的符号，原始 op.tsv 不变。所有正式作业使用同一网表核心哈希。', '',
        'CM/PSRR 测试的输出 DC 约为 0.929 V，而原标称伺服差分测试约为 0.900 V。本次增加完全相同 DC 偏置、仅改变 AC 刺激的差分参考；先核对节点与频率轴，再计算 Ad/Acm 或 Ad/Aps，没有直接把供电传递响应当抑制比。', '',
        '普通 noise 给出幅度谱密度，本报告积分其平方后开方。依据 [ngspice 官方噪声分析文档](https://nmg.gitlab.io/ngspice-manual/analysesandoutputcontrol_batchmode/analyses/noise_noiseanalysis.html)。噪声记录有 26 条 source/drain conductance reset 警告，全部保留；没有声称警告为零、开关噪声资格通过或 ADC SNDR 通过。', '',
        '## 可复现入口', '',
        '在已配置的本地 EDA 容器 `/repo` 中执行：', '', '```sh','python3 v2/verification/legacy_extra_20260913/run_campaign.py','python3 v2/verification/legacy_extra_20260913/run_rejection_reference.py','```', '',
        '两个命令均新建时间戳目录。把各自输出目录传给 `build_report.py --campaign ... --reference ...`，先校验原始文件哈希再生成新报告。这里的脚本依赖本地 ngspice/NumPy，不是供学校 Python 3.6.8 直接运行的上传包。', '',
        f'本报告已校验 {verified} 个来源/结果文件条目；完整目录见 [机器可读复核](review.json)、[32 项明细](jobs32.csv)。模型入口及递归 include 内容哈希、源文件快照、网表、所有工作点、曲线、日志、退出码保存在对应运行目录。', '',
        '学校端继续使用已验证的现有 extra 入口；本次没有覆盖学校 OA 库，也没有生成需要重新导入的旧 OTA 包。PVT 三项既有建立失败仍保留，旧 OTA 全指标达标状态不改变。','']
    (out/'复现报告.md').write_text('\n'.join(lines))
    put(out/'manifest.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'})
    print(json.dumps({'review':str(out),'summary':{k:report[k] for k in ['status','automatic_32_status_counts','rejection','noise','loads']}},indent=2,ensure_ascii=False))


if __name__=='__main__': main()
