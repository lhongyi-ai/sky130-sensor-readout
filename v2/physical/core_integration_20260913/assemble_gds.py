#!/usr/bin/env python3
"""Compose existing real macros as an explicitly UNROUTED assembly, without fake cells."""
import json
from pathlib import Path
import pya
from prepare import ROOT,HERE,sha

def box(b,dbu):return [round(v*dbu,6) for v in (b.left,b.bottom,b.right,b.top)]
def main():
    b=json.loads((HERE/'extracted_view_bindings.json').read_text())['bindings']
    layout=pya.Layout();layout.dbu=0.001
    for key in ['cdac','sampling_switch','digital']:
        src=pya.Layout();src.read(str(ROOT/b[key]['gds']))
        names={c.name for c in layout.each_cell()}
        collisions=names.intersection(c.name for c in src.each_cell())
        if collisions:raise RuntimeError('GDS name collision: '+str(collisions))
        layout.read(str(ROOT/b[key]['gds']))
    top=layout.create_cell('REUSABLE_MACROS_UNROUTED_20260913')
    entries=[('CDAC','cdac',0,0),('CLAMP_P','sampling_switch',20,452.5),('CLAMP_N','sampling_switch',481.6,452.5),('SAR_DIGITAL','digital',943.2,0)]
    instances=[];ports=[]
    for label,key,x,y in entries:
        cell=layout.cell(b[key]['gds_cell']);bb=cell.bbox()
        dx=round(x/layout.dbu)-bb.left;dy=round(y/layout.dbu)-bb.bottom
        transform=pya.Trans(dx,dy);top.insert(pya.CellInstArray(cell.cell_index(),transform))
        instances.append({'instance':label,'module':key,'source_cell':cell.name,'bbox_um':box(bb.transformed(transform),layout.dbu),'translation_um':[dx*layout.dbu,dy*layout.dbu]})
        for layer in layout.layer_indices():
            info=layout.get_info(layer)
            for shape in cell.shapes(layer).each():
                if shape.is_text() and shape.text.string in b[key]['pins']:
                    p=shape.text.trans.disp
                    ports.append({'instance':label,'pin':shape.text.string,'gds_layer':info.layer,'gds_datatype':info.datatype,'x_um':(p.x+dx)*layout.dbu,'y_um':(p.y+dy)*layout.dbu,'connected_by_top_routing':False})
    gds=HERE/'reusable_macros_UNROUTED.gds';layout.write(str(gds))
    verify=pya.Layout();verify.read(str(gds));vt=verify.cell(top.name)
    overlaps=[]
    for i,a in enumerate(instances):
      for b2 in instances[i+1:]:
        aa=a['bbox_um'];bb=b2['bbox_um']
        if max(aa[0],bb[0])<min(aa[2],bb[2]) and max(aa[1],bb[1])<min(aa[3],bb[3]):overlaps.append([a['instance'],b2['instance']])
    report={'status':'REAL_MACRO_ASSEMBLY_UNROUTED','gds_sha256':sha(gds),'top_cell':vt.name,'top_direct_instances':sum(1 for _ in vt.each_inst()),'bbox_um':box(vt.bbox(),verify.dbu),'instances':instances,'direct_pin_labels':ports,'overlap_pairs':overlaps,'gds_readback_pass':sum(1 for _ in vt.each_inst())==4 and not overlaps,'top_interconnect_count':0,'drc':None,'lvs':None,'top_pex':None,'full_core_complete':False,'scope':'Real existing macro GDS hierarchy only; no dummy placeholders, no missing analog blocks, no routing. Area is this provisional assembly only.'}
    (HERE/'assembly_readback.json').write_text(json.dumps(report,indent=2)+'\n')
    view=pya.LayoutView();view.load_layout(str(gds));view.max_hier();view.add_missing_layers();view.zoom_fit();view.save_image(str(HERE/'reusable_macros_UNROUTED.png'),2200,1100)
    print(json.dumps({k:report[k] for k in ['status','top_direct_instances','bbox_um','gds_readback_pass']}))
if __name__=='__main__':main()
