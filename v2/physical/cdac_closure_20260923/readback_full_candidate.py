#!/usr/bin/env python3
import argparse,collections,json,hashlib
from pathlib import Path
import klayout.db as kdb
p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();run=a.run.resolve();root=Path(__file__).resolve().parents[3]
ly=kdb.Layout();ly.read(str(run/'c3gap_diff.gds'));old=kdb.Layout();source=root/'v2/physical/cdac_route_20260911/artifacts/cdac_diff_routed.gds';old.read(str(source))
unit=ly.cell('mim_unit');oldunit=old.cell('mim_unit');assert unit and oldunit
keys={(ly.get_info(i).layer,ly.get_info(i).datatype) for i in ly.layer_indices()}|{(old.get_info(i).layer,old.get_info(i).datatype) for i in old.layer_indices()}
assert ly.dbu==old.dbu
for layer,dt in keys:
 li,oi=ly.find_layer(layer,dt),old.find_layer(layer,dt)
 r=kdb.Region(unit.begin_shapes_rec(li)) if li is not None else kdb.Region();o=kdb.Region(oldunit.begin_shapes_rec(oi)) if oi is not None else kdb.Region()
 assert (r^o).is_empty(),(layer,dt)
placement=json.loads((run/'placement.json').read_text());sides=[]
for side in ['P','N']:
 cell=ly.cell('c3gap_'+side.lower());insts=list(cell.each_inst());assert len(insts)==4356
 actual=collections.Counter((round(i.trans.disp.x*ly.dbu,5),round(i.trans.disp.y*ly.dbu,5)) for i in insts)
 expected=collections.Counter((u['x_um'],u['y_um']) for u in placement[side]);assert actual==expected
 assert all(ly.cell(i.cell_index).name=='mim_unit' for i in insts)
 box=cell.bbox();sides.append({'side':side,'unit_count':len(insts),'all_placement_coordinates_match':True,'bbox_um':[box.left*ly.dbu,box.bottom*ly.dbu,box.right*ly.dbu,box.top*ly.dbu]})
top=ly.cell('c3gap_diff');insts=list(top.each_inst());assert len(insts)==2
assert sorted((ly.cell(i.cell_index).name,round(i.trans.disp.x*ly.dbu,5),round(i.trans.disp.y*ly.dbu,5)) for i in insts)==[('c3gap_n',530.4,0),('c3gap_p',44.8,0)]
box=top.bbox();bbox=[box.left*ly.dbu,box.bottom*ly.dbu,box.right*ly.dbu,box.top*ly.dbu]
report={'status':'GDS_STRUCTURE_AND_UNIT_BODY_MATCH','MIM_child_polygons_identical_to_frozen_original':True,'original_gds_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'new_gds_sha256':hashlib.sha256((run/'c3gap_diff.gds').read_bytes()).hexdigest(),'sides':sides,'top_instances':2,'MIM_total':8712,'bbox_um':bbox,'width_um':box.width()*ly.dbu,'height_um':box.height()*ly.dbu,'area_um2':box.area()*ly.dbu**2,'scope':'Parent routing M3 fill is intentional and differs; MIM child bodies and placements checked independently.'}
(run/'full_gds_readback.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
