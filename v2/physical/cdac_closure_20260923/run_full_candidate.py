#!/usr/bin/env python3
"""Serial local-only full candidate DRC/LVS/C extraction, retaining failed runs."""
import argparse,re,shlex,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--container',default='sky130-v2-resume-20260910');a=p.parse_args();run=a.run.resolve();run.relative_to(HERE/'full_candidate')
assert (run/'manifest.json').is_file() and not any(run.glob('*.log')), 'Generate a new directory; old attempts are retained.'
crun=Path('/repo')/run.relative_to(ROOT)
def execute(args,log):
 with (run/log).open('x') as f:r=subprocess.run(['docker','exec',a.container,'bash','-lc',shlex.join(args)],stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise SystemExit(f'{log}: process exit{r.returncode}; results retained')
def stage(tag,cell):
 execute(['magic','-dnull','-noconsole','-rcfile','/foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc',str(crun/(tag+'.tcl'))],tag+'.log')
 if f'CANDIDATE_DRC_COUNT {tag.upper()} 0' not in (run/(tag+'.log')).read_text():raise SystemExit(f'{tag}: DRC not zero; stopped, no failed evidence overwritten.')
 execute(['netgen','-batch','lvs',str(crun/(cell+'.lvs.spice'))+' '+cell+'_flat',str(crun/(cell+'.reference.spice'))+' '+cell+'_flat','/foss/pdks/sky130A/libs.tech/netgen/sky130A_setup.tcl',str(crun/(tag+'_lvs.rpt')),'-json'],tag+'_netgen.log')
 if 'Final result: Circuits match uniquely.' not in (run/(tag+'_lvs.rpt')).read_text():raise SystemExit(f'{tag}: LVS not unique; stopped, evidence retained.')
for side in ['p','n']:stage(side,'c3gap_'+side)
subprocess.run([sys.executable,str(HERE/'prepare_full_top.py'),str(run)],check=True);stage('top','c3gap_diff')
execute(['python3',str(Path('/repo')/HERE.relative_to(ROOT)/'readback_full_candidate.py'),str(crun)],'full_gds_readback.log')
subprocess.run([sys.executable,str(HERE/'qualify_full_candidate.py'),str(run)],check=True)
