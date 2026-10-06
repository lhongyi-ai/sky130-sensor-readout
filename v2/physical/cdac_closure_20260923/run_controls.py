#!/usr/bin/env python3
"""Run a NEW local control directory in an EXISTING local public EDA container.
No image pulls/installs. Rejects any attempt that already has execution logs.
"""
import argparse,shlex,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--container',default='sky130-v2-resume-20260910');a=p.parse_args()
run=a.run.resolve();run.relative_to(HERE/'controls')
assert (run/'manifest.json').is_file()
assert not any(run.glob('*.log')), 'Existing attempt retained; generate a new directory.'
crun=Path('/repo')/run.relative_to(ROOT)
def execute(arguments,output):
 cmd=['docker','exec',a.container,'bash','-lc',shlex.join(arguments)]
 with (run/output).open('x') as f:ret=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 if ret.returncode:raise SystemExit(f'{output}: process exit{ret.returncode}; attempt retained')
for side in ('inside','outside'):
 execute(['magic','-dnull','-noconsole','-rcfile','/foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc',str(crun/(side+'.tcl'))],side+'.log')
 cell='p1cdac3_m5_'+side
 execute(['netgen','-batch','lvs',str(crun/(cell+'.lvs.spice'))+' '+cell+'_flat',str(crun/(cell+'.reference.spice'))+' '+cell+'_flat','/foss/pdks/sky130A/libs.tech/netgen/sky130A_setup.tcl',str(crun/(side+'_lvs.rpt')),'-json'],side+'_netgen.log')
execute(['python3',str(Path('/repo')/HERE.relative_to(ROOT)/'readback_controls.py'),str(crun)],'gds_readback.log')
subprocess.run([sys.executable,str(HERE/'qualify_controls.py'),str(run)],check=True)
