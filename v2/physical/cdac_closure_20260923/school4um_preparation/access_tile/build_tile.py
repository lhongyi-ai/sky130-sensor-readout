#!/usr/bin/env python3
"""Build isolated control inputs; do not create cells or run any CAD tool."""
from pathlib import Path
import copy,hashlib,json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
BASE=ROOT/'v2/physical/mim_adaptation_20260923'
CELL={'good':'p2c4_access_pair_r1','open':'p2c4_access_open_r1','short':'p2c4_access_short_r1'}

def rect(layer,bbox,net=None,role='routing'):
    return {'layer':layer,'bbox_um':bbox,'intended_net':net,'role':role}

def connected(a,b):
    return min(a[2],b[2])>=max(a[0],b[0]) and min(a[3],b[3])>=max(a[1],b[1])

def inside(point,box):
    x,y=point;return box[0]<=x<=box[2] and box[1]<=y<=box[3]

def audit(shapes,pins,case):
    # Rectangular ideal conductor topology only: explicitly distinguish CAPM top from M3 bottom.
    metal=[s for s in shapes if s['layer'] in ['met3','met4','met5','capm']]
    parent=list(range(len(metal)))
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def join(i,j):parent[root(i)]=root(j)
    for i,a in enumerate(metal):
        for j,b in enumerate(metal[:i]):
            if a['layer']==b['layer'] and connected(a['bbox_um'],b['bbox_um']):join(i,j)
    caps=[(i,x) for i,x in enumerate(metal) if x['layer']=='capm']
    assert len(caps)==2
    vias=[s for s in shapes if s['layer'] in ['via3','via4']]
    for via in vias:
        top_hit=[i for i,c in caps if connected(via['bbox_um'],c['bbox_um'])]
        a,b=('capm','met4') if via['layer']=='via3' and top_hit else ('met3','met4') if via['layer']=='via3' else ('met4','met5')
        ends=[[i for i,m in enumerate(metal) if m['layer']==l and connected(m['bbox_um'],via['bbox_um'])] for l in [a,b]]
        assert all(ends),('unlanded contact',via)
        for i in ends[0]:
            for j in ends[1]:join(i,j)
    port={}
    for name,layer,point in pins:
        ids=[i for i,m in enumerate(metal) if m['layer']==layer and inside(point,m['bbox_um'])]
        assert ids and len({root(i) for i in ids})==1
        port[name]=root(ids[0])
    terminals=[]
    for i,c in caps:
        bb=c['bbox_um'];mid=[(bb[0]+bb[2])/2,(bb[1]+bb[3])/2]
        bottoms=[j for j,m in enumerate(metal) if m['layer']=='met3' and inside(mid,m['bbox_um'])]
        assert len({root(j) for j in bottoms})==1
        terminals.append({'PLUS_component':root(i),'MINUS_component':root(bottoms[0])})
    assert all(t['PLUS_component']==port['TOP'] for t in terminals)
    if case=='good':
        assert len(set(port.values()))==3 and terminals[0]['MINUS_component']==port['BITA'] and terminals[1]['MINUS_component']==port['BITB']
    elif case=='open':
        assert len(set(port.values()))==3 and terminals[0]['MINUS_component']==port['BITA'] and terminals[1]['MINUS_component']!=port['BITB']
    else:
        assert port['BITA']==port['BITB']!=port['TOP'] and all(t['MINUS_component']==port['BITA'] for t in terminals)
    return {'status':'STATIC_RECTANGLE_CONNECTIVITY_MATCHES_INTENT','ports':port,'MIM_terminals':terminals,
            'MIM_devices':2,'MIM_via3_count':162,'ordinary_via3_count':2,'via4_count':sum(v['layer']=='via4' for v in vias),
            'expected_PVS_LVS':'MATCH' if case=='good' else 'MISMATCH','actual_PVS_LVS':'NOT_RUN','actual_DRC':'NOT_RUN'}

def main():
    geom=next(x for x in json.loads((BASE/'array_geometry_manifest.json').read_text()) if x['name']=='p1ma_array4_r1')
    metadata=json.loads((HERE/'school_contact_metadata.json').read_text())
    assert metadata['technology_sha256']=='f28f7fdd87d3b11fa3123b34d5722dab89b67214d61f3dc3f1e3c2af6123fc78'
    lookup={x['line']:x for x in metadata['constraints']}
    for line,nums in [(1546,[.06,.09]),(1547,[.065,.065]),(1549,[.19,.19]),(1550,[.31,.31]),(1652,[.2]),(1663,[.8]),(1667,[1.6])]:assert lookup[line]['numeric_values']==nums
    shapes=[]
    for dx,net in [(0,'BITA'),(12,'BITB')]:
        for layer,purpose,lo,hi in geom['shapes']:
            shapes.append(rect(layer,[lo[0]+dx,lo[1],hi[0]+dx,hi[1]],net if layer=='met3' else 'TOP','frozen_4um_body'))
    # Generous control spacing, not a final array pitch: full unchanged 4um MIM bodies.
    shapes += [rect('met4',[3.7,1.7,12.3,2.3],'TOP','common_top_bridge'),
               rect('met4',[1.7,3.7,2.3,6.3],'TOP','top_pin_access'),
               rect('met3',[-4.3,1.7,-.2,2.3],'BITA','bottom_escape'),
               rect('met3',[16.2,1.7,20.3,2.3],'BITB','bottom_escape')]
    for x,net in [(-4,'BITA'),(20,'BITB')]:
        # 0.2 ordinary via3 has >=0.10 M3 and 0.50 M4 enclosure.
        # 0.8 via4 has 0.20 M4 and 0.40 M5 enclosure; via cuts remain outside CAPM.
        shapes += [rect('met3',[x-.2,1.8,x+.2,2.2],net,'via3_bottom_landing'),
                   rect('via3',[x-.1,1.9,x+.1,2.1],net,'ordinary_via3'),
                   rect('met4',[x-.6,1.4,x+.6,2.6],net,'isolated_intermediate_landing'),
                   rect('via4',[x-.4,1.6,x+.4,2.4],net,'ordinary_via4'),
                   rect('met5',[x-.8,-4.8,x+.8,2.8],net,'external_trunk')]
    shapes += [rect('met5',[-10.8,-4.8,-3.2,-3.2],'BITA','row_end_turn'),
               rect('met5',[19.2,-4.8,26.8,-3.2],'BITB','row_end_turn')]
    pins=[['TOP','met4',[2,6]],['BITA','met5',[-10,-4]],['BITB','met5',[26,-4]]]
    helper=(ROOT/'v2/physical/mim_qualification_r3_20260923/layout_helper.il').read_text()
    helper=helper.replace('p1r3Layout','p2c4Layout').replace('mim_qualification_r3','cdac4_access_preparation_r1')
    skill=[helper,'; All targets isolated. Refuses existing cells. No schematic/model mutation.']
    configs={};checks={}
    for case,name in CELL.items():
        ss=copy.deepcopy(shapes)
        if case=='open':ss=[s for s in ss if not(s['role']=='ordinary_via4' and s['intended_net']=='BITB')]
        if case=='short':ss.append(rect('met3',[4.2,-.3,11.8,.3],'SHORT_AB','intentional_short'))
        configs[case]={'cell':name,'shapes':ss,'pins':pins,'actual_execution':'NOT_RUN','nominal_device_dimensions_um':[4,4],
                       'unit_origins_um':[[0,0],[12,0]],'control_spacing_not_array_pitch':True}
        checks[case]=audit(ss,pins,case)
        def pair(x):return 'list('+ ' '.join(f'{v:.6f}' for v in x)+')'
        rects='list('+ ' '.join('list("'+s['layer']+'" "drawing" '+pair(s['bbox_um'][:2])+' '+pair(s['bbox_um'][2:])+')' for s in ss)+')'
        ps='list('+ ' '.join('list("'+n+'" "'+l+'" '+pair(pt)+')' for n,l,pt in pins)+')'
        skill += ['p2c4Layout("'+name+'" '+rects+' '+ps+')']
        # Reference deliberately represents the expected GOOD connection for all cases.
        cdl=['* Project-owned two-capacitor connectivity fixture; not ADC replacement.',
             '.SUBCKT p1_mim_public_r1 PLUS MINUS','.ENDS p1_mim_public_r1',
             '.SUBCKT '+name+' TOP BITA BITB','XXA TOP BITA / p1_mim_public_r1 w=4u l=4u',
             'XXB TOP BITB / p1_mim_public_r1 w=4u l=4u','.ENDS '+name]
        (HERE/(case+'.cdl')).write_text('\n'.join(cdl)+'\n')
    skill += ['printf("P2C4_ACCESS_CREATED_NOT_VERIFIED\\n")']
    (HERE/'create_access_tiles.il').write_text('\n'.join(skill)+'\n')
    (HERE/'control_geometry.json').write_text(json.dumps({'status':'PREPARED_NOT_RUN','formal_ADC_PEX_allowed':False,'cases':configs},indent=2)+'\n')
    (HERE/'local_geometry_check.json').write_text(json.dumps({'scope':'Ideal rectangle connectivity only; not DRC/LVS','cases':checks},indent=2)+'\n')
    maps=['met3 drawing 70 20','met3 pin 70 16','met3 label 70 5','met4 drawing 71 20','met4 pin 71 16','met4 label 71 5',
          'met5 drawing 72 20','met5 pin 72 16','met5 label 72 5','via3 drawing 70 44','via4 drawing 71 44','capm drawing 89 44']
    (HERE/'access.map').write_text('\n'.join(maps)+'\n')
    rules=HERE/'rules';rules.mkdir(exist_ok=True)
    origin=BASE/'pvs_research'
    layers=(origin/'mim_layers.pvl').read_text()+('\n// Local control extension, mapped against school metadata; not signoff.\n'
        'layer_map 71 -datatype 44 107144;\nlayer_map 72 -datatype 20 107220;\nlayer_map 72 -texttype 5 107205;\n'
        'layer_def P1_VIA4 107144;\nlayer_def P1_M5 107220;\nlayer_def P1_M5_TEXT 107205;\n')
    (rules/'mim_layers.pvl').write_text(layers)
    (rules/'mim_drc.pvl').write_text((origin/'mim_drc.pvl').read_text())
    lvs=(origin/'mim_lvs.pvl').read_text().replace('text_layer P1_M3_TEXT P1_M4_TEXT;','text_layer P1_M3_TEXT P1_M4_TEXT P1_M5_TEXT;')
    lvs=lvs.replace('attach P1_M4_TEXT P1_M4;','attach P1_M4_TEXT P1_M4;\nattach P1_M5_TEXT P1_M5;')
    lvs=lvs.replace('port -text_layer P1_M3_TEXT P1_M4_TEXT;','port -text_layer P1_M3_TEXT P1_M4_TEXT P1_M5_TEXT;')
    lvs=lvs.replace('connect P1_M3 P1_M4 -by P1_ROUTING_VIA3;','connect P1_M3 P1_M4 -by P1_ROUTING_VIA3;\nconnect P1_M4 P1_M5 -by P1_VIA4;')
    (rules/'mim_lvs.pvl').write_text(lvs)
    (HERE/'preparation_status.json').write_text(json.dumps({'status':'PREPARED_NOT_RUN','local_geometry_checks':'PASS_INTENT_ONLY','native_cell_creation':'NOT_RUN',
        'DRC':'NOT_RUN','LVS':'NOT_RUN','PEX':'NOT_RUN','formal_ADC_PEX_allowed':False,
        'proposed_unit_origin_separation_um':12,'final_array_pitch_um':None,
        'model_change':'None. References use isolated project probe primitive; current ADC untouched.',
        'Copper_branch':'No Copper selection or areaid.mt marker added. Runtime branch must be recorded; do not claim .2/.210 alone proves violation.',
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'array_geometry_manifest.json',origin/'mim_layers.pvl',origin/'mim_lvs.pvl',origin/'mim_drc.pvl']}},indent=2)+'\n')
    print('PREPARED_NOT_RUN: 3 isolated access controls; actual CAD execution remains NOT_RUN.')

if __name__=='__main__':main()
