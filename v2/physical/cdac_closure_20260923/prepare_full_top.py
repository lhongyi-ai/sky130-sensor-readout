#!/usr/bin/env python3
import sys
sys.dont_write_bytecode=True
import argparse,json
from pathlib import Path
import generate_full_candidate as gen
p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();run=a.run.resolve()
for side in ('p','n'):
 assert f'CANDIDATE_DRC_COUNT {side.upper()} 0' in (run/(side+'.log')).read_text()
 assert 'Final result: Circuits match uniquely.' in (run/(side+'_lvs.rpt')).read_text()
assert not (run/'top.tcl').exists()
origins={'P':44.8,'N':530.4};lines=gen.HEADER+['load c3gap_diff -silent','box values 0 0 0 0']
ports=[];idx=1
for side,x0 in origins.items():
 lines +=[f'getcell c3gap_{side.lower()} child 0 0 parent {x0}um 0um; identify X_{side}']
 defs=[('TOP','metal3',x0+gen.old.x_c2(1),gen.cy(1))]+[(net,'metal4',x0+gen.old.PIN_X,gen.PERIPH[net]) for net in gen.old.NETS_DESC]+[('EDGE_BIAS','metal3',x0+gen.old.x_c2(0),0)]
 for net,layer,x,y in defs:
  name=side+'_'+net;ports.append(name)
  lines +=[gen.rect(layer,x-.2,y-.2,x+.2,y+.2),gen.pin(name,idx,layer,x,y)];idx+=1
lines +=['save c3gap_diff','select top cell','expand','drc on','drc style drc(full)','drc check','drc catchup','puts "CANDIDATE_DRC_COUNT TOP [drc list count total]"','puts "CANDIDATE_DRC_DETAILS TOP [drc listall why]"','gds write c3gap_diff.gds','drc off','flatten c3gap_diff_flat','load c3gap_diff_flat','save c3gap_diff_flat','extract all','ext2spice lvs','ext2spice -o c3gap_diff.lvs.spice','ext2spice cthresh 0','ext2spice rthresh 0','ext2spice -o c3gap_diff.cap.spice','quit -noprompt']
(run/'top.tcl').write_text('\n'.join(lines)+'\n')
placement=json.loads((run/'placement.json').read_text());ref=['.subckt c3gap_diff_flat '+' '.join(ports)]
for side,units in placement.items():
 for u in units:
  ref +=[f'X{side}_r{u["row"]:02d}_c{u["col"]:02d}_{u["net"]} {side}_'+(u['net'] if u['electrical'] else 'EDGE_BIAS')+' '+side+'_'+('TOP' if u['electrical'] else 'EDGE_BIAS')+' sky130_fd_pr__cap_mim_m3_1 w=3 l=3']
ref +=['.ends'];(run/'c3gap_diff.reference.spice').write_text('\n'.join(ref)+'\n')
print(run/'top.tcl')
