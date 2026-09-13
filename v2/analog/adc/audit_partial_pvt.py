#!/usr/bin/env python3
"""Account for retained results of the intentionally stopped old 90-point run.

This script launches no simulator and cannot mark the planned matrix complete.
"""
import json
import re

from run_adc import RESULTS, table, interp, LSB


def main():
    rows=[]
    for path in sorted(RESULTS.glob('preamp_float_*.tsv')):
        name=path.stem
        m=re.fullmatch(r'preamp_float_(tt|ff|ss|fs|sf)_([0-9.]+)_(-?[0-9]+)_(-?1)',name)
        if not m:continue
        corner,vdd,temp,sign=m.groups();vdd=float(vdd);sign=int(sign)
        data=table(name);log=(RESULTS/(name+'.log')).read_text()
        provenance=json.loads((RESULTS/(name+'.provenance.json')).read_text())
        complete=bool(data[-1,0]>=3.2e-6-1e-14 and 'ngspice-47 done' in log and not re.search(r'(?im)^\s*(error:|fatal error|doanalyses:|timestep too small)',log))
        row=dict(name=name,corner=corner,vdd=vdd,temperature_c=int(temp),input_diff_v=sign*LSB/4,
                 simulator_exit_code_collected=provenance.get('status')=='SIMULATED',recorded_status=provenance.get('status'),
                 complete_output_observed=complete,last_recorded_time_s=float(data[-1,0]))
        if complete:
            out=interp(data,3.02e-6,5)-interp(data,3.02e-6,6)
            held=interp(data,3.15e-6,5)-interp(data,3.15e-6,6)
            row.update(output_diff_v=out,decision_pass=bool(out*sign>.8*vdd),held=bool(held*sign>.8*vdd))
        rows.append(row)
    summary=dict(status='INTENTIONALLY_STOPPED_OLD_CANDIDATE_MATRIX_INCOMPLETE',planned_cases=90,
                 cases_with_waveforms=len(rows),complete_output_cases=sum(r['complete_output_observed'] for r in rows),
                 cases=rows,full_matrix_pass=False,
                 scope='Old bottom-preamp wrapper with standard reference TGs, fixed1.1/.7V references, only code2048 +/- quarter LSB. Not new LVT-reference combo.',
                 reason='Subsequent isolated MSB tests established standard-Vt low-voltage cold acquisition/reference-settling failure; parent prioritized the corrected combo instead of spending more time on an unqualified old candidate.',
                 note='The scheduling-interruption cases retain complete written waveforms/log completion markers but their process exit code was not collected. They are separately labeled, never silently promoted to a complete 90-case regression.')
    (RESULTS/'preamp_floating_pvt_partial_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='cases'},indent=2))


if __name__=='__main__':main()
