#!/usr/bin/env python3
"""Read the two already-run PZ logs. Never rerun or certify their root lists."""
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def parse_poles(text):
    matches=re.finditer(r'pole\((\d+)\)\s*=\s*('+NUMBER+r')(?:\s*,\s*('+NUMBER+r'))?',text)
    return [{'index':int(m.group(1)),'real_per_s':float(m.group(2)),
             'imag_rad_per_s':float(m.group(3) or 0)} for m in matches]


def classify(text):
    poles=parse_poles(text)
    nonfinite=bool(re.search(r'(?i)Reference value\s*:\s*(?:nan|inf)',text))
    return {'status':'NATIVE_PZ_OUTPUT_NUMERICALLY_UNVALIDATED',
            'native_log_finished':'ngspice-47 done' in text,
            'reported_pole_count':len(poles),'reported_rhp_count':sum(p['real_per_s']>0 for p in poles),
            'nonfinite_progress_value_seen':nonfinite,
            'roots_residual_validated':False,'complete_stability_qualified':False,'reported_poles':poles}


def main():
    paths=[]
    for gain in [1,16]:
        matches=sorted((HERE/'results').glob(f'*/g{gain}/console.txt'))
        if len(matches)!=1:raise ValueError(f'Expected exactly one simulation for gain {gain}')
        paths.append(matches[0])
    rows=[]
    for gain,logpath in zip([1,16],paths):
        text=logpath.read_text();row=classify(text)
        folder=logpath.parent
        runpath=folder/'run.json'
        row.update(gain=gain,path=str(folder.relative_to(HERE)),
            source_sha256=hashlib.sha256((folder/'candidate.spice').read_bytes()).hexdigest(),
            log_sha256=hashlib.sha256(logpath.read_bytes()).hexdigest(),
            poles_raw_sha256=hashlib.sha256((folder/'poles.raw').read_bytes()).hexdigest(),
            operating_point_sha256=hashlib.sha256((folder/'operating_point.tsv').read_bytes()).hexdigest(),
            native_run=json.loads(runpath.read_text()) if runpath.exists() else {
                'returncode':None,'reason':'G1 simulation finished and printed done; its Python parser failed before persisting return code. No rerun.'})
        (folder/'audited_summary.json').write_text(json.dumps(row,indent=2)+'\n')
        rows.append(row)
    result={'status':'NATIVE_CLOSED_LOOP_PZ_ATTEMPT_COMPLETE_NUMERICAL_QUALIFICATION_INCOMPLETE',
            'circuit_runs':2,'maximum_allowed_each_s':120,'gains':rows,
            'same_frozen_candidate':len({row['source_sha256'] for row in rows})==1,
            'complete_stability_qualified':False,
            'interpretation':'The native algorithm returned pole lists with suspicious diagnostics. Without residual/eigenmode validation, neither their RHP entries nor absence of other modes proves circuit behavior.',
            'official_reference':{'url':'https://ngspice.sourceforge.io/docs/ngspice-manual.pdf',
                'section':'1.2.4 Pole-Zero Analysis, PDF page 41; 11.3.6 .PZ',
                'paraphrase':'Native numerical search can miss roots or return an excessive number of apparent roots.'},
            'conditions':{'corner':'tt','vdd_v':1.8,'temp_c':27,'input_cm_v':.9,'differential_input_v':0,
                'source_r_each_ohm':350,'pdk_isolation_r_each_ohm':2600,'pdk_filter_nominal_each_pf':4,
                'pdk_static_mim_load_each_pf':81.28512,'port':'pz fp 0 fp 0 cur pol'},
            'not_claimed':['No proof of genuine RHP modes from these lists alone.',
                'No blanket stable verdict even if a future list contains only LHP roots.',
                'No guarantee of controllability/observability for every CM and bias state.',
                'No clocked-load, large-signal, startup, PVT, mismatch or extracted-layout stability qualification.'],
            'tooling_incidents':['Interactive help query without an X server failed; capability checked in primary manual and actual batch PZ runs.',
                'G1 result parser initially failed to parse positive exponent signs; fixed offline without rerunning the circuit.'],
            'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'cases':[{k:r[k] for k in ['gain','reported_pole_count','reported_rhp_count','nonfinite_progress_value_seen']} for r in rows]},indent=2))


if __name__=='__main__':main()
