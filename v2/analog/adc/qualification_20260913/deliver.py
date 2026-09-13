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
    rows=['| Profile | Actual runtime | Result | Complete conversions / real decisions |', '|---|---:|---|---:|']
    for item in summaries:
        rows.append(f"| {item['profile']} | {item['wall_seconds']:.3f} s | {item['status']} | {len(item['codes'])} / {item['accepted_decisions']} |")
    detail=''
    if numeric.get('channels'):
        cdac=numeric['channels']['cdac_differential']
        detail=(f"\nDifferential CDAC error: maximum {cdac['union_grid_max_error_v']*1e6:.6f} µV "
            f"({cdac['union_grid_max_error_lsb']:.6f} LSB) on the union of accepted timepoints; maximum {cdac['common_1ns_max_error_v']*1e6:.6f} µV on the common 1 ns grid; "
            f"maximum {cdac['predecision_max_error_v']*1e6:.6f} µV across all predecision checkpoints. "
            "The strict threshold remains 0.05 LSB = 9.765625 µV. Small predecision errors and identical output codes do not override the complete-waveform failure.\n")
    budget=result.get('measured_cost_extrapolation',{})
    estimate=(f"Extrapolating from the slowest completed profile in this round, 131073 continuous conversions without warmup would take approximately {budget.get('continuous_131073_points_days',0):.2f} days; "
        f"the current batch=8 scheme with warmup and previous-point replay approximately {budget.get('ramp_batch8_including_warmup_and_history_days',0):.2f} days; "
        f"and one continuous record of 16384 points plus 256 warmup conversions approximately {budget.get('single_16384_plus_256_warmup_record_days',0):.2f} days. "
        "This is a linear resource estimate from one measurement, not a runtime commitment or full-PVT budget.") if budget else ''
    text='''# ADC local circuit-level progress report (2026-09-13)

**The 12 frames agree functionally, but the numerical waveforms have not converged, so reliable continuous conversion cannot be considered qualified.** The maximum difference between the same physical differential CDAC nodes in the two runs is **48.393 mV** on the union of accepted timepoints; it remains **4.077 mV** on the common **1 ns** grid. Both greatly exceed **0.05 LSB = 9.765625 µV**.

This round covers positive and negative near-full-scale inputs, both sides of zero, several new code centers, and large alternating jumps. Full ADC qualification remains incomplete; all-code coverage, long-record spectra, and complete ADC mismatch have not been falsely reported as passing.

'''+ '\n'.join(rows)+f'''

Each complete run lasts 122 µs at 100 kS/s, resets only once, and retains all 12 frames. Conditions are TT, 1.8 V, 27 °C, 350 Ω per input, and reference sources of 1 Ω + 10 nF. The real SKY130 CDAC, switches, preamplifier, dynamic comparator, and SAR RTL are retained, using the local bridge with the repaired 33-bit output mask.

Output codes are cross-checked among the actual bus, RTL log, and 144 Q/QB decision windows; 50 ready/busy state points are checked independently. Ideal codes are diagnostic only and do not determine real comparator results. Each simulation's original netlist, waveforms, logs, exit code, and hashes are in its corresponding results/ directory.

Numerical-comparison status: **{numeric['status']}**. baseline uses a 2 ns maximum timestep and reltol=1e-5; strict uses a 1 ns maximum timestep and tightens reltol/abstol/vntol tenfold.
{detail}
{estimate}

The all-code plan remains fixed at 4096 × 32 + 1 = **131073 points**, with **0 points** completed. The campaign.py run entry point was observed to exit with code 2, keeping the quality gate closed. The plan and underlying resume protocol retain one worker, preserved failures, explicit retries, and at most one batch per invocation. This version does not allow long runs; new numerical qualification requires a separately auditable version and must not modify existing failed results.

campaigns/spectrum_and_mismatch.json fixes the constraints for a continuous sine record of **16384 points**, bin=7373, 45001.220703125 Hz, and −1 dBFS, plus a requirement for **200 independent complete-ADC mismatch samples**. These are unexecuted requirement descriptions. A deterministic FFT is not SNDR with device noise; independently reset short records cannot be concatenated into a continuous spectrum. The historical 200-case CDAC and 200-case comparator statistics are not full-ADC mismatch samples.

The existing real CDAC PEX still fails monotonicity in all-4096-code static linearity. It is a dependency for subsequent complete-ADC post-layout simulation; this directory has changed neither its layout nor its conclusion.

## Reproduction and limits of migration to the university environment

The only qualified runtime environment is the existing local Linux AArch64 container with its frozen ngspice/PDK. The bridge binary is ELF e_machine=183 (ARM64) and cannot directly serve as an x86_64 university Linux executable. run_checked.py explicitly rejects an incorrect architecture and verifies the hashes of the actually loaded helpers, RTL, circuit, and bridge. The runner rechecks PDK and tool identities. The supplementary helper audit in support/ is byte-for-byte consistent with the original frozen source; this supplementary audit was recorded after the baseline run.

Execute under /repo in the existing container:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py check
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py baseline
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py strict
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/campaign.py collect
```

Each of the two real experiment profiles saves a new independent result directory and is limited to 900 s per run; collect should currently exit with code 2 and report 0/131073. Migration to the university environment still requires rebuilding the bridge for its architecture, actual university models and licenses, Spectre syntax/model verification, and initial qualification of short handshake and conversion tests. This directory contains no Spectre batch job that bypasses university-environment qualification.

## Evidence entry points

- report.json: all actual runs, numerical results, budgets, historical-evidence boundaries, ABI, and validation exit codes.
- snapshot/manifest.json and support/manifest.json: source hashes for the circuit, RTL, repaired bridge, PDK/tool records, and analysis helpers.
- numerical_comparison.json: strict numerical comparisons on the union of accepted timepoints and the common 1 ns grid.
- peak_diagnosis/: both raw time axes around the largest error, voltages at the same physical TP/TN nodes, and digital/real phase-edge locations; the specific mechanism causing this error has not yet been isolated.
- results/*/conversion_table.csv: per-frame input, actual output code, comparator word, and valid time.
- validation/: actual output from negative software tests, the closed quality gate, zero all-code coverage, and source/architecture checks. These software tests are not additional circuit samples.
- solver_probe/: a separate KLU operating-point capability diagnostic; operating-point completion does not establish transient speed or numerical qualification. See the [official ngspice description](https://ngspice.sourceforge.io/applic.html) for the option basis.

Still incomplete: complete all-code INL/DNL, long-record spectra with device noise, 200 complete-ADC mismatch cases, full PVT, full-ADC post-parasitic qualification, and university Cadence qualification.
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
