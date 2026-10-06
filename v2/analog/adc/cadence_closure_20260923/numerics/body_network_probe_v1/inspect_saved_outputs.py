#!/usr/bin/env python3
"""Check only whether requested diagnostic observations actually exist."""
from collections import Counter
import json
from pathlib import Path
import re

ROOT=Path.cwd()
primitive='p2_ams_reset1.phases.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8'
raw=ROOT/'amsdControl.raw/adc_closure_tran.tran.tran'
section='header';signals={};last_time=None
with raw.open() as f:
    for line in f:
        line=line.strip()
        if line=='TRACE':section='trace';continue
        if line=='VALUE':section='value';continue
        if section=='trace':
            m=re.match(r'^"([^"]+)"\s+"([^"]+)"',line)
            if m:signals[m[1]]=m[2]
        if section=='value':
            m=re.match(r'^"time"\s+(\S+)',line)
            if m:last_time=float(m[1])
requested={key:[n for n in signals if n in (primitive+'.'+key,primitive+':'+key)] for key in ['int_b','dbnode','sbnode','vds','reversed']}
currents={n:k for n,k in signals.items() if n.startswith(primitive) and k=='I'}
log=(ROOT/'xrun.log').read_text(errors='replace')
warnings=dict(Counter(re.findall(r'WARNING \(([^)]+)\)',log)))
issues=[]
for key,found in requested.items():
    if len(found)!=1:issues.append('Missing/ambiguous saved '+key)
if len(currents)<4:issues.append('Fewer than four confirmed primitive terminal-current traces; inspect actual labels/types')
if last_time is None or abs(last_time-4.1e-6)>1e-15:issues.append('Requested 4.1us diagnostic interval not complete')
if (ROOT/'simulator_exit_code.txt').read_text().strip()!='0':issues.append('Simulator did not complete successfully')
if any(warnings.get(c,0) for c in ['SFE-3453','SPECTRE-8282']):issues.append('Requested observations were rejected/skipped')
report={'status':'OBSERVABILITY_ONLY_OK_NOT_QUALIFIED' if not issues else 'OBSERVABILITY_INCOMPLETE_NOT_QUALIFIED','issues':issues,'requested_trace_names':requested,'actual_terminal_current_traces':currents,'all_primitive_prefixed_traces':{n:k for n,k in signals.items() if n.startswith(primitive)},'waveform_stop_s':last_time,'warnings':warnings,'full_ADC_accuracy_pass':False,'limitations':['This is a short observation probe; protocol qualification exit2 is expected.','No absence of warnings, complete node inventory or terminal-current conservation grants an ADC numerical PASS.','If a documented field was not saved, preserve this attempt and resolve its actual supported name; never synthesize a replacement trace.']}
(ROOT/'body_observability_review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(0 if not issues else 2)
