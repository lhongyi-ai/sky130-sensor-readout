#!/usr/bin/env python3
"""Summarize actual immutable runs, gate outcomes and bounded software checks."""
import csv
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import qualify as q
import campaign

def main():
    q.verify()
    out=q.HERE/'validation'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    checks=[]
    commands=[['-m','unittest','discover','-s',str(q.HERE),'-p','test_*.py','-v'],
              [str(q.HERE/'campaign.py'),'run'],[str(q.HERE/'campaign.py'),'collect'],
              [str(q.HERE/'run_checked.py'),'check']]
    for index,args in enumerate(commands):
        process=subprocess.run([sys.executable,*args],text=True,capture_output=True,timeout=90,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        log=out/f'check_{index}.log';log.write_text(process.stdout+process.stderr)
        checks.append({'command':[sys.executable,*args],'returncode':process.returncode,
            'expected_returncode':0 if index in (0,3) else 2,'log':str(log.relative_to(q.HERE)),
            'log_sha256':q.sc.sha(log)})
    write=q.write
    write(out/'checks.json',checks)
    summaries=[]
    for path in sorted(q.HERE.glob('results/*/summary.json')):
        record=json.loads(path.read_text());raw=(path.parent/'native.log').read_text(errors='replace')
        def measure(name):
            found=re.search(re.escape(name)+r'\s*=\s*([\d.eE+-]+)',raw)
            return float(found.group(1)) if found else None
        brief={k:record.get(k) for k in ('status','profile','wall_seconds','returncode','rows','accepted_decisions','checks','stop_us','interval_max_deviation_ns')}
        brief.update(path=str(path.relative_to(q.HERE)),sha256=q.sc.sha(path),
            codes=[frame['log_code'] for frame in record.get('frames',[])],
            waveform_bytes=(path.parent/'waveform.dat').stat().st_size if (path.parent/'waveform.dat').exists() else None,
            engine={key:measure(key) for key in ('Total analysis time (seconds)','Matrix load time',
                'Matrix factor time','Matrix solve time','Circuit Equations','Accepted timepoints','Rejected timepoints')})
        summaries.append(brief)
        if record.get('frames'):
            with (path.parent/'conversion_table.csv').open('w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=list(record['frames'][0]))
                writer.writeheader();writer.writerows(record['frames'])
    numeric_path=q.HERE/'numerical_comparison.json'
    numeric=json.loads(numeric_path.read_text()) if numeric_path.exists() else {'status':'NOT_COMPLETED'}
    audit=[]
    for name in ('cdac_mismatch_summary.json','comparator_mismatch_summary.json'):
        path=q.ADC/'results'/name;r=json.loads(path.read_text());r.pop('samples',None)
        audit.append({'file':str(path),'file_sha256':q.sc.sha(path),'historical_summary':r,
            'adc_blocks_hash_matches_composite':r['source_sha256']==q.sc.sha(q.HERE/'snapshot/frozen/adc_blocks.spice'),
            'whole_adc_mismatch_evidence':False})
    pex=q.ADC/'cdac_pex_linearity_20260911/qualification.json'
    result={'status':'BOUNDED_LOCAL_PROGRESS_FULL_ADC_INCOMPLETE',
        'source_snapshot_sha256':q.sc.sha(q.HERE/'snapshot/manifest.json'),
        'support_helper_manifest_sha256':q.sc.sha(q.HERE/'support/manifest.json'),
        'runs':summaries,'numerical_comparison':numeric,'gate':campaign.gate(),
        'solver_probes':[dict(json.loads(p.read_text()),summary_path=str(p.relative_to(q.HERE)),summary_sha256=q.sc.sha(p))
            for p in sorted(q.HERE.glob('solver_probe/*/summary.json'))],
        'validation':checks,'historical_mismatch_audit':audit,
        'physical_dependency':{'qualification':str(pex),'sha256':q.sc.sha(pex),
            'status':json.loads(pex.read_text()).get('status'),
            'scope':'existing routed CDAC static PEX dependency; not changed here'},
        'full_static_grid_completed_points':0,'fft_completed_record_samples':0,
        'whole_adc_mismatch_samples_completed':0,'complete_adc_qualified':False,
        'spectre_or_school_host_qualified':False,
        'binary_abi':{'format':'ELF64 little endian','e_machine':183,'architecture':'AArch64',
            'os_qualified_here':'Linux','x86_64_school_binary_compatible':False,
            'required_next_step':'rebuild corrected bridge on school architecture and qualify short live handshake/conversion case'}}
    passed=[s for s in summaries if s['status']=='CONTINUOUS_12_FRAME_FUNCTIONAL_PASS']
    if passed:
        slowest=max(s['wall_seconds'] for s in passed); per=slowest/12
        result['measured_cost_extrapolation']={'basis':'slowest completed 12-frame run; one run/profile under current machine load, not a guaranteed bound',
            'seconds_per_conversion':per,'continuous_131073_points_days':per*131073/86400,
            'ramp_batch8_including_warmup_and_history_days':per*(2*131073+16384)/86400,
            'single_16384_plus_256_warmup_record_days':per*(16384+256)/86400,
            'unchanged_waveform_storage_for_131073_conversions_bytes':max(s['waveform_bytes'] for s in passed)/12*131073}
    write(q.HERE/'report.json',result)
    rows=['| 配置 | 实际耗时 | 结果 | 完整转换 / 真实判决 |', '|---|---:|---|---:|']
    for item in summaries:
        rows.append(f"| {item['profile']} | {item['wall_seconds']:.3f} s | {item['status']} | {len(item['codes'])} / {item['accepted_decisions']} |")
    detail=''
    if numeric.get('channels'):
        cdac=numeric['channels']['cdac_differential']
        detail=(f"\nCDAC 差分误差：接受点联合时间格最大 {cdac['union_grid_max_error_v']*1e6:.6f} µV"
            f"（{cdac['union_grid_max_error_lsb']:.6f} LSB）；公共 1 ns 格最大 {cdac['common_1ns_max_error_v']*1e6:.6f} µV；"
            f"全部判决前检查点最大 {cdac['predecision_max_error_v']*1e6:.6f} µV。"
            "严格门限保持 0.05 LSB = 9.765625 µV。小的判决前误差和相同输出码不能覆盖全波形失败。\n")
    budget=result.get('measured_cost_extrapolation',{})
    estimate=(f"按本轮最慢完成配置外推，131073 次无预热连续转换约 {budget.get('continuous_131073_points_days',0):.2f} 天；"
        f"当前 batch=8、预热与前一点回放方案约 {budget.get('ramp_batch8_including_warmup_and_history_days',0):.2f} 天；"
        f"16384 点加 256 次预热的一条连续记录约 {budget.get('single_16384_plus_256_warmup_record_days',0):.2f} 天。"
        "这只是一次实测的线性资源估计，不是运行承诺，也不是全 PVT 预算。") if budget else ''
    text='''# ADC 本地电路级推进报告（2026-09-13）

**12 帧功能一致，但数值波形未收敛，不能认定可靠连续转换已验收。** 两组同一物理 CDAC 差分节点的最大差为 **48.393 mV**（联合接受时间点格）；在公共 **1 ns** 时间格上仍为 **4.077 mV**，均远超 **0.05 LSB = 9.765625 µV** 门限。

本轮覆盖正负近满量程、零点两侧、多个新码中心和大幅交替跳变。完整 ADC 验收仍未完成；全码、长记录频谱和完整 ADC 失配均未冒充通过。

'''+ '\n'.join(rows)+f'''

每次完整运行均为 122 µs、100 kS/s；只复位一次，全部 12 帧均保留。TT、1.8 V、27 °C、350 Ω/端、参考源 1 Ω + 10 nF。真实 SKY130 CDAC、开关、前放、动态比较器及 SAR RTL 均保留，使用已修复 33 位输出掩码的本地桥。

输出码由实际总线、RTL 日志、144 个 Q/QB 判决窗口互相核验；50 个 ready/busy 状态点独立检查。理想码仅作诊断，不决定真实比较器结果。每次仿真原始网表、波形、日志、退出码和哈希均在 results/ 对应目录。

数值对照状态：**{numeric['status']}**。baseline 使用 2 ns 最大步长及 reltol=1e-5；strict 使用 1 ns 最大步长，并将 reltol/abstol/vntol 全部收紧十倍。
{detail}
{estimate}

全码计划固定为 4096 × 32 + 1 = **131073 点**，当前完成 **0 点**。campaign.py 的 run 入口实测退出 2，保持质量门关闭；计划与单 worker、保留失败、显式重试、每次最多一批的底层恢复协议已保留。此版本不开放长跑，新的数值资格必须另立可审计版本，不能修改已有失败结果。

campaigns/spectrum_and_mismatch.json 固定了 **16384 点**、bin=7373、45001.220703125 Hz、−1 dBFS 的连续正弦记录约束，以及 **200 个完整 ADC 独立失配样本**要求。它们是未执行的约束描述。确定性 FFT 不作为含器件噪声 SNDR；独立复位的短记录不能拼成连续频谱。旧 CDAC 和比较器分别 200 例的统计结果均不是完整 ADC 失配样本。

现有真实 CDAC PEX 的全 4096 码静态线性仍有单调性失败；它是后续完整 ADC 后仿的依赖项，本目录未修改其版图或结论。

## 复现与学校迁移边界

唯一已验证运行环境是现有本地 Linux AArch64 容器及其冻结的 ngspice/PDK。桥二进制 ELF e_machine=183（ARM64），不能直接作为 x86_64 学校 Linux 可执行文件。run_checked.py 会明确拒绝错误架构，并核验实际加载的助手文件、RTL、电路和桥哈希。PDK 与工具身份由运行器再次检查。support/ 中的补充助手审计与原有冻结源码逐字节一致；该补充审计记录在 baseline 运行之后。

在现有容器 /repo 下执行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py check
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py baseline
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py strict
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/campaign.py collect
```

前两类真实实验每次保存新的独立结果目录，单次最多 900 s；collect 当前应退出 2 并报告 0/131073。学校迁移还需对应架构重建桥、实际学校模型及许可、Spectre 语法/模型验证，以及先完成短握手与转换资格；本目录没有未经学校验证的 Spectre 批量任务。

## 证据入口

- report.json：全部实际运行、数值结果、预算、历史证据边界、ABI 与验证退出码。
- snapshot/manifest.json、support/manifest.json：电路、RTL、已修复桥、PDK/工具记录与分析助手源哈希。
- numerical_comparison.json：联合接受点时间格及公共 1 ns 时间格的严格数值比较。
- peak_diagnosis/：最大误差附近两组原始时间轴、同一物理 TP/TN 节点电压、数字/真实相位边沿位置；尚未隔离造成该误差的具体机制。
- results/*/conversion_table.csv：逐帧输入、真实输出码、比较器字及 valid 时间。
- validation/：软件负面测试、质量门关闭、全码零覆盖、源/架构检查的实际输出。这些软件测试不是新增电路样本。
- solver_probe/：单独的 KLU 工作点能力诊断；不将工作点完成算成瞬态速度或数值资格。选项依据见 [ngspice 官方说明](https://ngspice.sourceforge.io/applic.html)。

未完成项仍是：完整全码 INL/DNL、含器件噪声的长记录频谱、200 例完整 ADC 失配、完整 PVT、整个 ADC 寄生后验收以及学校 Cadence 资格。
'''
    (q.HERE/'README.md').write_text(text)
    files={str(p.relative_to(q.HERE)):{'sha256':q.sc.sha(p),'bytes':p.stat().st_size}
        for p in sorted(q.HERE.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts and p.name!='worker.lock'}
    # Include source manifests explicitly; only this inventory excludes itself.
    for path in (q.HERE/'snapshot/manifest.json',q.HERE/'support/manifest.json'):
        files[str(path.relative_to(q.HERE))]={'sha256':q.sc.sha(path),'bytes':path.stat().st_size}
    write(q.HERE/'manifest.json',{'files':files,'complete_adc_qualified':False})
    return 0 if all(c['returncode']==c['expected_returncode'] for c in checks) else 2

if __name__=='__main__':raise SystemExit(main())
