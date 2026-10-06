#!/usr/bin/env python3
"""Prepare isolated 2x2 access controls. No remote command or CAD execution."""
from pathlib import Path
import collections,copy,datetime,hashlib,importlib.util,json,math,shutil,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
R1=HERE.parent/'access_tile'
NAMES={k:'p2c4_quad_'+k+'_r2' for k in ['good','open','short']}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):(HERE/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def hit(a,b):return min(a[2],b[2])>=max(a[0],b[0]) and min(a[3],b[3])>=max(a[1],b[1])
def inside(pt,b):return b[0]<=pt[0]<=b[2] and b[1]<=pt[1]<=b[3]

def geometry_audit(shapes,pins,key):
    metals=[s for s in shapes if s['layer'] in ['met3','met4','met5','capm']]
    parent=list(range(len(metals)))
    def root(i):
        while i!=parent[i]:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def join(i,j):parent[root(i)]=root(j)
    for i,a in enumerate(metals):
        for j,b in enumerate(metals[:i]):
            if a['layer']==b['layer'] and hit(a['bbox_um'],b['bbox_um']):join(i,j)
    caps=[(i,s) for i,s in enumerate(metals) if s['layer']=='capm'];assert len(caps)==4
    vias=[s for s in shapes if s['layer'] in ['via3','via4']]
    for s in vias:
        cap_hit=[i for i,c in caps if hit(s['bbox_um'],c['bbox_um'])]
        ends=('met4','met5') if s['layer']=='via4' else ('capm','met4') if cap_hit else ('met3','met4')
        ids=[[i for i,m in enumerate(metals) if m['layer']==l and hit(m['bbox_um'],s['bbox_um'])] for l in ends]
        assert all(ids),('unlanded contact',s)
        for i in ids[0]:
            for j in ids[1]:join(i,j)
    ports={}
    for n,l,point in pins:
        ids=[i for i,m in enumerate(metals) if m['layer']==l and inside(point,m['bbox_um'])]
        assert len({root(i) for i in ids})==1
        ports[n]=root(ids[0])
    devices=[]
    for i,c in caps:
        b=c['bbox_um'];pt=[(b[0]+b[2])/2,(b[1]+b[3])/2]
        ids=[j for j,m in enumerate(metals) if m['layer']=='met3' and inside(pt,m['bbox_um'])]
        assert len({root(j) for j in ids})==1
        devices.append({'origin_um':b[:2],'PLUS_component':root(i),'MINUS_component':root(ids[0]),'w_um':b[2]-b[0],'l_um':b[3]-b[1]})
    assert all(d['w_um']==d['l_um']==4 for d in devices)
    byorigin={tuple(d['origin_um']):d for d in devices}
    for pos,net in [((0,0),'B00'),((12,0),'B01'),((0,12),'B10'),((12,12),'B11')]:
        assert byorigin[pos]['MINUS_component']==ports[net]
    if key=='good':
        assert len(set(ports.values()))==5 and all(d['PLUS_component']==ports['TOP'] for d in devices)
    elif key=='open':
        assert len(set(ports.values()))==5
        assert byorigin[(0,0)]['PLUS_component']==byorigin[(12,0)]['PLUS_component']!=ports['TOP']
        assert byorigin[(0,12)]['PLUS_component']==byorigin[(12,12)]['PLUS_component']==ports['TOP']
    else:
        assert ports['B00']==ports['B10'] and len(set(ports.values()))==4 and all(d['PLUS_component']==ports['TOP'] for d in devices)
    comps={root(i) for i in range(len(metals))}
    expected={'good':5,'open':6,'short':4}[key];assert len(comps)==expected
    return {'status':'STATIC_RECTANGLE_TOPOLOGY_MATCHES_INTENT','scope':'Generated ideal conductor connectivity only, not DRC/LVS/PEX',
            'component_count':len(comps),'port_components':ports,'MIM_devices':devices,'expected_actual_layout_external_ports':4 if key=='short' else 5,
            'expected_PVS_LVS':'MATCH' if key=='good' else 'MISMATCH','PVS_LVS':'NOT_RUN'}

LAYER={'met3':70,'met4':71,'met5':72,'via3':70,'via4':71,'capm':89}
def gds_real8(v):
    if not v:return bytes(8)
    sign=128 if v<0 else 0;v=abs(v);ex=64
    while v>=1:v/=16;ex+=1
    while v<1/16:v*=16;ex-=1
    return bytes([sign+ex])+round(v*2**56).to_bytes(7,'big')
def rec(typ,dtype,data=b''):
    if len(data)%2:data+=b'\0'
    return struct.pack('>HBB',len(data)+4,typ,dtype)+data
def i2(*v):return struct.pack('>'+'h'*len(v),*v)
def write_gds(path,cell,shapes,pins):
    # Local project-owned preview only; native stream-out is required for real verification.
    date=[2026,9,24,0,0,0]*2
    b=rec(0,2,i2(600))+rec(1,2,i2(*date))+rec(2,6,b'P2C4_QUAD_R2')+rec(3,5,gds_real8(.001)+gds_real8(1e-9))
    b+=rec(5,2,i2(*date))+rec(6,6,cell.encode())
    def polygon(layer,dt,box):
        x1,y1,x2,y2=box;pts=[x1,y1,x2,y1,x2,y2,x1,y2,x1,y1]
        assert all(math.isclose(x*1000,round(x*1000),abs_tol=1e-7) for x in pts)
        return rec(8,0)+rec(13,2,i2(layer))+rec(14,2,i2(dt))+rec(16,3,struct.pack('>10i',*(round(x*1000) for x in pts)))+rec(17,0)
    for s in shapes:b+=polygon(LAYER[s['layer']],44 if s['layer'] in ['via3','via4','capm'] else 20,s['bbox_um'])
    for name,layer,(x,y) in pins:
        b+=polygon(LAYER[layer],16,[x-.01,y-.01,x+.01,y+.01])
        b+=rec(12,0)+rec(13,2,i2(LAYER[layer]))+rec(22,2,i2(5))+rec(16,3,struct.pack('>2i',round(x*1000),round(y*1000)))+rec(25,6,name.encode())+rec(17,0)
    b+=rec(7,0)+rec(4,0);path.write_bytes(b)

def main():
    if (HERE/'actual_execution_review.json').exists():raise RuntimeError('Do not overwrite a reviewed delivery. Create a new version.')
    previous=json.loads((R1/'actual_execution_review.json').read_text());assert previous['status']=='SCOPED_ACCESS_GEOMETRY_AND_LVS_VERIFIED'
    inputs=[R1/'control_geometry.json',R1/'actual_execution_review.json',R1/'actual_evidence_manifest.json',R1/'create_access_tiles.il',R1/'access.map',R1/'run_checks.py',
            R1/'school_via_exclusion_resolved_metadata.json']+[R1/'rules'/x for x in ['mim_layers.pvl','mim_drc.pvl','mim_lvs.pvl']]
    frozen={str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in inputs}
    manifest=HERE/'source_manifest.json'
    if manifest.exists():assert json.loads(manifest.read_text())==frozen,'Frozen R1 evidence changed'
    else:save('source_manifest.json',frozen)
    original=json.loads((R1/'control_geometry.json').read_text())['cases']['good']['shapes']
    shapes=[]
    for row,dy in [(0,0),(1,12)]:
        for src in original:
            if src['role']=='top_pin_access':continue
            dst=copy.deepcopy(src);b=dst['bbox_um'];dst['bbox_um']=[round(v,6) for v in [b[0],b[1]+dy,b[2],b[3]+dy]]
            dst['intended_net']={'BITA':'B'+str(row)+'0','BITB':'B'+str(row)+'1'}.get(src['intended_net'],src['intended_net'])
            dst['source_row']=row;shapes.append(dst)
    shapes += [{'layer':'met4','bbox_um':[7.7,1.7,8.3,14.3],'intended_net':'TOP','role':'cross_row_top_bridge'},
               {'layer':'met4','bbox_um':[7.7,14.1,8.3,18.3],'intended_net':'TOP','role':'top_port_access'}]
    pins=[['TOP','met4',[8,18]],['B00','met5',[-10,-4]],['B01','met5',[26,-4]],['B10','met5',[-10,8]],['B11','met5',[26,8]]]
    helper=(R1/'create_access_tiles.il').read_text().split('; All targets isolated.')[0]
    helper=helper.replace('p2c4Layout','p2c4QuadLayout').replace('cdac4_access_preparation_r1','cdac4_shared_access_r2')
    skill=[helper,'; Refuse ALL existing targets before creating any cell. No old cell/model edits.',
           'foreach(name list('+ ' '.join('"'+n+'"' for n in NAMES.values())+') when(ddGetObj("project1" name) error("Refuse existing target: %s" name)))']
    cases={};audits={};gds=HERE/'local_gds_preview';gds.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('prep',HERE.parent/'prepare.py');prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)
    gds_audits={}
    for key,name in NAMES.items():
        ss=copy.deepcopy(shapes)
        if key=='open':ss=[s for s in ss if s['role']!='cross_row_top_bridge']
        elif key=='short':ss.append({'layer':'met3','bbox_um':[1.7,4.2,2.3,11.8],'intended_net':'SHORT_B00_B10','role':'intentional_cross_row_bottom_short'})
        cases[key]={'cell':name,'shapes':ss,'pins':pins,'unit_origins_um':[[0,0],[12,0],[0,12],[12,12]],'model_unit_dimensions_um':[4,4],
                    'control_spacing_not_final_array_pitch':True,'actual_execution':'NOT_RUN'}
        audits[key]=geometry_audit(ss,pins,key)
        def pair(v):return 'list('+ ' '.join(f'{x:.6f}' for x in v)+')'
        rectangles='list('+ ' '.join('list("'+s['layer']+'" "drawing" '+pair(s['bbox_um'][:2])+' '+pair(s['bbox_um'][2:])+')' for s in ss)+')'
        ps='list('+ ' '.join('list("'+n+'" "'+l+'" '+pair(pt)+')' for n,l,pt in pins)+')'
        skill.append('p2c4QuadLayout("'+name+'" '+rectangles+' '+ps+')')
        cdl=['* Project-owned shared-access topology fixture. Not an ADC model replacement.','.SUBCKT p1_mim_public_r1 PLUS MINUS','.ENDS p1_mim_public_r1',
             '.SUBCKT '+name+' TOP B00 B01 B10 B11']
        cdl += ['XX'+str(i)+' TOP '+n+' / p1_mim_public_r1 w=4u l=4u' for i,n in enumerate(['B00','B01','B10','B11'])]
        cdl += ['.ENDS '+name];(HERE/(key+'.cdl')).write_text('\n'.join(cdl)+'\n')
        out=gds/(name+'.gds');write_gds(out,name,ss,pins)
        cn,dbu,items=prep.flat_gds(out);assert cn==[name] and math.isclose(dbu,1e-9)
        actual=collections.Counter((x['layer'],x['datatype'],tuple(prep.bbox(x['points_um']))) for x in items if x['kind']=='polygon' and x['datatype']!=16)
        expected=collections.Counter((LAYER[s['layer']],44 if s['layer'] in ['via3','via4','capm'] else 20,tuple(round(v,9) for v in s['bbox_um'])) for s in ss)
        assert actual==expected
        assert {e['text']:e['points_um'][0] for e in items if e['kind']=='text'}=={n:pt for n,l,pt in pins}
        gds_audits[key]={'status':'LOCAL_PREVIEW_READBACK_MATCH','source':'LOCAL_GENERATOR_NOT_NATIVE_STREAM_OUT','drawing_rectangles':len(ss),'sha256':sha(out),
                         'MIM_count':4,'MIM_internal_via3':324,'ordinary_via3':4,'ordinary_via4':4,'pin_count':5}
    skill.append('printf("P2C4_QUAD_CREATED_NOT_VERIFIED\\n")');(HERE/'create_access_tiles.il').write_text('\n'.join(skill)+'\n')
    save('control_geometry.json',{'status':'PREPARED_NOT_RUN','formal_ADC_PEX_allowed':False,'cases':cases})
    save('local_geometry_check.json',{'status':'STATIC_TOPOLOGY_INTENT_PASS_NOT_DRC_LVS','cases':audits})
    save('local_gds_readback.json',gds_audits)
    for rel in ['access.map','run_checks.py','school_via_exclusion_resolved_metadata.json','rules/mim_layers.pvl','rules/mim_lvs.pvl','rules/mim_drc.pvl']:
        dest=HERE/rel;dest.parent.mkdir(exist_ok=True);shutil.copyfile(R1/rel,dest)
    save('preparation_status.json',{'status':'PREPARED_NOT_RUN','native_creation':'NOT_RUN','DRC':'NOT_RUN','LVS':'NOT_RUN','PEX':'NOT_RUN','formal_ADC_PEX_allowed':False,
         'nominal_device_count':4,'bottom_port_count':4,'common_port':'TOP on M4','source_multiplicity':'four explicit instances, no m parameter',
         'unit_origin_separation_xy_um':[12,12],'final_array_pitch_um':None,'edge_dummy_present':False,'school_model_modified':False,
         'rule_change_from_passed_r1':'NONE; project rules, map and serial runner copied byte-for-byte',
         'scope':'Shared M4 top across two rows with M3 separate bottoms and CAPM-external via3/via4 M5 row ends. No absolute CAPM coupling/RC boundary qualification.'})
    print('PREPARED_NOT_RUN: three 2x2 controls, four explicit MIM each; local geometry and GDS preview readback passed.')

if __name__=='__main__':main()
