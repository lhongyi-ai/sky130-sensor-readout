#!/usr/bin/env python3
"""Independent flattened GDS geometry equality check, using KLayout only."""
import argparse, hashlib,json
from pathlib import Path
import klayout.db as kdb
p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();run=a.run
layouts=[];items=[]
for label in ('inside','outside'):
 path=run/f'p1cdac3_m5_{label}.gds';ly=kdb.Layout();ly.read(str(path));cell=ly.cell(f'p1cdac3_m5_{label}')
 refs=list(cell.each_inst()); assert len(refs)==128 and all(ly.cell(i.cell_index).name=='mim_unit' for i in refs)
 texts=[]
 for li in ly.layer_indices():
  it=cell.begin_shapes_rec(li)
  while not it.at_end():
   sh=it.shape()
   if sh.is_text():texts.append({'layer':str(ly.get_info(li)),'text':sh.text.string,'position':str(it.trans()*sh.text.trans.disp)})
   it.next()
 layouts.append((ly,cell))
 items.append({'case':label,'gds_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'dbu_um':ly.dbu,'instances':len(refs),'MIM_transforms':sorted(str(i.trans) for i in refs),'top_port_labels':[t for t in texts if t['text'] in ('TOP','BIT','AGG')]})
assert items[0]['MIM_transforms']==items[1]['MIM_transforms']
all_layers=sorted(set((layouts[0][0].get_info(i).layer,layouts[0][0].get_info(i).datatype) for i in layouts[0][0].layer_indices()) | set((layouts[1][0].get_info(i).layer,layouts[1][0].get_info(i).datatype) for i in layouts[1][0].layer_indices()))
xors=[]
for layer,dt in all_layers:
 regs=[]
 for ly,cell in layouts:
  li=ly.find_layer(layer,dt)
  regs.append(kdb.Region(cell.begin_shapes_rec(li)).merged() if li is not None else kdb.Region())
 xor=regs[0]^regs[1]
 xors.append({'gds_layer':layer,'datatype':dt,'inside_area_um2':regs[0].area()*layouts[0][0].dbu**2,'outside_area_um2':regs[1].area()*layouts[1][0].dbu**2,'xor_area_um2':xor.area()*layouts[0][0].dbu**2})
changed=[d for d in xors if d['xor_area_um2']]
assert {(d['gds_layer'],d['datatype']) for d in changed}=={(72,20),(72,16)},changed
drawing=next(d for d in changed if d['datatype']==20)
assert abs(drawing['xor_area_um2']-614.4)<1e-8
assert abs(drawing['inside_area_um2']-drawing['outside_area_um2'])<1e-8
assert abs(next(d for d in changed if d['datatype']==16)['xor_area_um2']-.08)<1e-8
report={'status':'GDS_ONLY_M5_AGGRESSOR_POSITION_CHANGED','cases':items,'layer_geometry_comparison':xors,'claim':'All non-M5 drawing polygons identical; MIM placement identical; M5 area identical; two disjoint192x1.6 rectangles account for the conductor XOR difference. The AGG M5 pin marker (72/16) also moves; its XOR is0.08um2. Text excluded from polygon areas.','not_claimed':['independent physical capacitance calibration','school4x4 layout compatibility']}
(run/'gds_readback.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'changed':changed}))
