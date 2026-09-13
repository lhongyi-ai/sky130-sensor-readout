#!/usr/bin/env python3
"""Preserve both original local time grids and physical-node peak context."""
import csv
import json
import numpy as np
import qualify as q

def main():
    record=json.loads((q.HERE/'numerical_comparison.json').read_text())
    centre=record['channels']['cdac_differential']['worst_time_s']
    out=q.HERE/'peak_diagnosis';out.mkdir(exist_ok=True)
    lo,hi=centre-10e-9,centre+10e-9
    signals=['xadc.tp','xadc.tn','sample','top_sample','acq','conv','evaluate','trial11','rp','rn','vcm']
    result={'same_physical_nodes':['XADC.TP','XADC.TN'],
        'difference_definition':'V(XADC.TP) - V(XADC.TN), same node names and same frozen core in both runs',
        'centre_s':centre,'window_s':[lo,hi],'runs':[],
        'interpretation':'Strict finite-waveform comparison fails. Local accepted grids and phase crossings are diagnostics; no cause has been isolated and no waveform-error waiver is applied.'}
    for profile,path_name in [('baseline','reference'),('strict','candidate')]:
        directory=q.Path(record[path_name]);deck=(directory/'adc.spice').read_text()
        names=q.tr.save_vectors(deck);values=np.loadtxt(directory/'waveform.dat',skiprows=1);t=values[:,0]
        columns=[names.index('v('+n+')')+1 for n in signals]
        use=(t>=lo)&(t<=hi);local=values[use]
        with (out/(profile+'_original_points.csv')).open('w',newline='') as handle:
            writer=csv.writer(handle);writer.writerow(['original_time_s',*signals,'cdac_differential_v'])
            for row in local:writer.writerow([row[0],*[row[c] for c in columns],row[21]-row[22]])
        # The wider edge window includes the physical switching sequence.
        edge_lo,edge_hi=13.49e-6,13.56e-6
        edges={}
        for name,column in zip(signals,columns):
            if name not in ('sample','top_sample','acq','conv','evaluate','trial11'):continue
            v=values[:,column]
            rise=q.tr.tc.crossings(t,v,.9);fall=q.tr.tc.crossings(t,1.8-v,.9)
            edges[name]={'rising_50percent_s':rise[(rise>=edge_lo)&(rise<=edge_hi)].tolist(),
                         'falling_50percent_s':fall[(fall>=edge_lo)&(fall<=edge_hi)].tolist()}
        result['runs'].append({'profile':profile,'summary_sha256':q.sc.sha(directory/'summary.json'),
            'netlist_sha256':q.sc.sha(directory/'adc.spice'),'waveform_sha256':q.sc.sha(directory/'waveform.dat'),
            'original_points_in_window':len(local),'local_step_min_s':float(np.diff(local[:,0]).min()),
            'local_step_max_s':float(np.diff(local[:,0]).max()),
            'values_at_worst_common_time_v':{n:float(np.interp(centre,t,values[:,c])) for n,c in zip(signals,columns)},
            'edge_window_s':[edge_lo,edge_hi],'physical_and_digital_edges':edges})
    result['output_sha256']={p.name:q.sc.sha(p) for p in out.iterdir() if p.is_file()}
    result['runner_sha256']=q.sc.sha(__file__)
    q.write(out/'diagnosis.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
