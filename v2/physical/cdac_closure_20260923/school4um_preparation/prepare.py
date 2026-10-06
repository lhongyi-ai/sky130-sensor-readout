#!/usr/bin/env python3
"""Read project-owned evidence and emit an unplaced, unqualified 4um CDAC plan.

No PDK import, remote command, simulator, layout generation or rule assumption.
GDS reader deliberately supports only the flat rectangles/text in this probe.
"""
from pathlib import Path
import collections
import csv
import hashlib
import json
import math
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ADAPT = ROOT / 'v2/physical/mim_adaptation_20260923'
MAPPING = ROOT / 'v2/physical/cdac_repair_20260923/adc_native_mapping_1'
OLD = HERE.parent / 'full_candidate/run_20260924T022452Z_44370b78'
NATIVE = ADAPT / 'native_evidence/export_native_20260923T170014011349Z/array4'
INPUTS = [ADAPT/'array_geometry_manifest.json', ADAPT/'public_mim.map',
          NATIVE/'layout.gds', NATIVE/'cdl/source.cdl', NATIVE/'spectre/netlist',
          ADAPT/'report.json', ADAPT/'model_research/README.md',
          ADAPT/'create_schematics.il', ADAPT/'create_layouts.il',
          MAPPING/'reset1/native_audit.json', MAPPING/'reset1/objects.json',
          MAPPING/'private_runtime/si_reset1_001/netlist',
          ROOT/'v2/analog/adc/cadence_closure_20260923/integration/reset1_2frames_baseline_v4/manifest.json',
          ROOT/'v2/cadence/linuxlab_20260923/runs/spectre_mapping_20260923T100217323690Z/mapping_metrics.json',
          OLD/'placement.json', OLD/'qualification.json', OLD/'manifest.json']


def dump(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def real8(b):
    if not any(b):
        return 0.0
    return (-1 if b[0] & 128 else 1) * (int.from_bytes(b[1:], 'big') / 2**56) * 16**((b[0] & 127)-64)


def flat_gds(path):
    data = path.read_bytes()
    offset, element, meters, ended = 0, None, None, False
    cells, elements = [], []
    while offset+4 <= len(data):
        size, typ, dtype = struct.unpack('>HBB', data[offset:offset+4])
        assert size >= 4 and size % 2 == 0 and offset+size <= len(data)
        body = data[offset+4:offset+size]
        offset += size
        if typ == 3:
            meters = real8(body[8:])
        elif typ == 6:
            cells.append(body.rstrip(b'\0').decode())
        elif typ in [8, 12]:
            assert element is None
            element = {'kind': 'polygon' if typ == 8 else 'text'}
        elif typ in [9, 10, 11, 45]:
            raise ValueError('Unsupported GDS element in flat reference')
        elif typ == 13:
            element['layer'] = struct.unpack('>h', body)[0]
        elif typ in [14, 22]:
            element['datatype'] = struct.unpack('>h', body)[0]
        elif typ == 16:
            xy = struct.unpack('>'+str(len(body)//4)+'i', body)
            element['points_um'] = [[round(xy[i]*meters*1e6, 9), round(xy[i+1]*meters*1e6, 9)] for i in range(0, len(xy), 2)]
        elif typ == 25:
            element['text'] = body.rstrip(b'\0').decode()
        elif typ == 17:
            assert element is not None
            elements.append(element)
            element = None
        elif typ == 4:
            ended = True
            break
    assert ended and not any(data[offset:]) and element is None
    return cells, meters, elements


def bbox(points):
    return [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]


def logical_lines(path):
    return path.read_text().replace('\\\n', ' ').splitlines()


def main():
    hashes = {str(p.relative_to(ROOT)): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in INPUTS}
    lock = HERE/'source_manifest.json'
    if lock.exists():
        assert json.loads(lock.read_text()) == hashes, 'Frozen input changed; review instead of silently reusing.'
    else:
        dump('source_manifest.json', hashes)

    unit = next(x for x in json.loads((ADAPT/'array_geometry_manifest.json').read_text()) if x['name'] == 'p1ma_array4_r1')
    assert unit['w_um'] == unit['l_um'] == 4 and unit['via_count'] == 81
    mapping = {('met3','drawing'):(70,20), ('capm','drawing'):(89,44), ('met4','drawing'):(71,20), ('via3','drawing'):(70,44)}
    cells, meters, elements = flat_gds(NATIVE/'layout.gds')
    assert cells == ['p1ma_array4_r1']
    actual = collections.Counter((e['layer'],e['datatype'],tuple(bbox(e['points_um']))) for e in elements if e['kind']=='polygon' and e['datatype']!=16)
    expected = collections.Counter((*mapping[(l,p)],tuple(lo+hi)) for l,p,lo,hi in unit['shapes'])
    assert actual == expected, 'Actual native GDS differs from geometry manifest'
    # Ensure each polygon is a rectangle, rather than accepting bbox equality alone.
    for e in elements:
        if e['kind']=='polygon':
            p=e['points_um']; b=bbox(p)
            assert len(p)==5 and p[0]==p[-1]
            assert set(map(tuple,p[:-1]))=={(b[0],b[1]),(b[2],b[1]),(b[2],b[3]),(b[0],b[3])}
    pins = {}
    for name, layer, xy in unit['pins']:
        gds_layer = 71 if layer=='met4' else 70
        texts = [e for e in elements if e['kind']=='text' and e.get('text')==name]
        assert len(texts)==1 and texts[0]['layer']==gds_layer and texts[0]['datatype']==5 and texts[0]['points_um']==[xy]
        box=[round(xy[0]-.01,9),round(xy[1]-.01,9),round(xy[0]+.01,9),round(xy[1]+.01,9)]
        assert sum(e['kind']=='polygon' and e['layer']==gds_layer and e['datatype']==16 and bbox(e['points_um'])==box for e in elements)==1
        pins[name]={'layer':layer,'gds':[gds_layer,16],'bbox_um':box,'label_um':xy,'orientation':'R0','meaning':'top electrode' if name=='PLUS' else 'bottom electrode'}
    assert 'X0 (PLUS MINUS) p1_mim_public_r1 w=4u l=4u' in (NATIVE/'spectre/netlist').read_text()
    facts={'status':'ACTUAL_NATIVE_GDS_READBACK_MATCH', 'cell':cells[0], 'body_bbox_um':[-.4,-.4,4.4,4.4], 'capm_dimensions_um':[4,4],
           'body_center_um':[2,2], 'gds_database_unit_m':meters,'via3_count':81,'via3_grid':[9,9], 'via3_cut_um':[.2,.2], 'via3_pitch_um':[.4,.4],
           'via3_first_lower_left_um':[.3,.3], 'via3_last_upper_right_um':[3.7,3.7], 'bottom_enclosure_um':.4,'top_plate_bbox_um':[.1,.1,3.9,3.9],
           'drawing_layers':{k[0]:list(v) for k,v in mapping.items()},'pins':pins,
           'model':'p1_mim_public_r1','outer_multiplier_supported':False,'model_scope':'TT nominal isolated public wrapper; no statistics/full-PVT equivalence to school cap_mim_m3_1 asserted',
           'internal_effective_contact_count_is_not_81':True,'formal_ADC_PEX_allowed':False}
    dump('school_unit_facts.json',facts)

    audit=json.loads((MAPPING/'reset1/native_audit.json').read_text())
    assert audit['actual_count']==audit['expected_count']==693 and audit['error_count']==0
    instances=[x for x in audit['instances'] if x['kind']=='mim']
    assert len(instances)==30
    export={}
    for line in logical_lines(MAPPING/'private_runtime/si_reset1_001/netlist'):
        m=re.match(r'^(\S+)\s+\(([^)]+)\)\s+(cap_mim_m3_1)\s+(.*)$',line)
        if m:
            export[m[1]]={'nodes':m[2].split(),'model':m[3],'params':dict(re.findall(r'(\w+)\s*=\s*([^\s]+)',m[4]))}
    assert len(export)==30
    cdac={}; rows=[]
    for x in instances:
        e=export[x['name']]
        assert e['nodes']==x['nodes'] and e['params']==x['exported_parameters'] and x['terminal_order']==['PLUS','MINUS']
        assert e['params']['w']==e['params']['l']=='4u'
        m=re.match(r'XADC_XC([PN])_X(C(\d+)|D)_XC$',x['name'])
        role='CDAC' if m else 'comparator/preamp load'
        row={'instance':x['name'],'role':role,'model':e['model'],'PLUS_node':e['nodes'][0],'MINUS_node':e['nodes'][1],'w_um':4,'l_um':4,'parallel_units':int(e['params']['m'])}
        rows.append(row)
        if m:
            side=m[1]; net='DUMMY' if m[2]=='D' else 'B'+m[3]
            assert row['parallel_units']==(1 if net=='DUMMY' else 2**int(net[1:]))
            assert row['PLUS_node']=='XADC_T'+side
            assert row['MINUS_node']==('XADC_D'+side if net=='DUMMY' else 'XADC_B'+side+net[1:])
            cdac[(side,net)]=row
    assert len(cdac)==26
    for side in ['P','N']:
        assert sum(x['parallel_units'] for (s,n),x in cdac.items() if s==side)==4096
    with (HERE/'adc_capacitor_mapping.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    measured=json.loads(INPUTS[13].read_text())['measured_capacitance_F']
    ratio=measured['CBANK']/measured['CUNIT']
    assert math.isclose(ratio,4096,rel_tol=1e-6)
    dump('adc_mapping_summary.json',{'status':'NATIVE_SOURCE_AND_CDF_AUDIT_MATCH','ADC_primitive_count':693,'ADC_MIM_instances':30,
         'CDAC_MIM_instances':26,'CDAC_units_per_side':4096,'CDAC_units_total':8192,'other_ADC_MIM_instances':4,'other_ADC_MIM_units':40,
         'phase_block_excluded':{'primitive_count':48,'MIM_count':3,'dimensions_um':[22.215,22.215],'reason':'Separate phase generator, outside 693 ADC and CDAC scope'},
         'm_semantics':'Each CDAC bank is m parallel 4x4 model units; do not replace by one rectangle or interpret m as via count',
         'actual_school_1kHz_AC_unit_F':measured['CUNIT'],'actual_school_1kHz_AC_bank_F':measured['CBANK'],'actual_bank_over_unit':ratio,
         'unit_bank_probe_limit':'One school model AC test; not layout RC/stats validation, not a guarantee at all frequencies/corners',
         'critical_orientation':{'native_ADC_COMMON':'PLUS=top M4','native_ADC_BIT':'MINUS=bottom M3',
             'old_3um_route_COMMON':'C2=bottom M3','old_3um_route_BIT':'C1=top M4','direct_scaled_reuse_allowed':False},
         'school_ADC_model':'cap_mim_m3_1','project_unit_model':'p1_mim_public_r1','interchangeability_qualified':False,'formal_ADC_PEX_allowed':False})

    placement=json.loads((OLD/'placement.json').read_text());plan=[]
    for side,units in placement.items():
        for u in units:
            electrical=u['electrical']; record=cdac[(side,u['net'])] if electrical else None
            row=int(u['row']);col=int(u['col'])
            gcoef=.5 if electrical and u['net'] in ['B0','DUMMY'] else (1 if row>=33 else 0)
            plan.append({'side':side,'row':row,'col':col,'assignment':u['net'],'electrical':int(electrical),
                'PLUS_node':record['PLUS_node'] if record else 'EDGE_BIAS_UNRESOLVED',
                'MINUS_node':record['MINUS_node'] if record else 'EDGE_BIAS_UNRESOLVED',
                'model_units':1,'width_um':4,'length_um':4,'orientation':'R0',
                'center_x_pitch_coefficient':col,'center_y_pitch_coefficient':row,'center_y_channel_coefficient':gcoef,
                'native_origin_dx_from_center_um':-2,'native_origin_dy_from_center_um':-2})
        for net in ['B'+str(i) for i in range(12)]+['DUMMY']:
            assert sum(u['electrical'] and u['net']==net for u in units)==cdac[(side,net)]['parallel_units']
        assert sum(not u['electrical'] for u in units)==260
    with (HERE/'unplaced_assignment.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(plan[0]));w.writeheader();w.writerows(plan)
    dump('routing_requirements.json',{'status':'PARAMETERIZED_UNPLACED_ONLY','actual_native_body_width_height_um':[4.8,4.8],
         'pitch_x_um':None,'pitch_y_um':None,'center_channel_height_um':None,'side_separation_um':None,'full_area_um2':None,
         'coordinate_rule':'center=(col*pitch_x, row*pitch_y + gap_coefficient*center_channel_height); native CAPM lower-left=center-(2,2)',
         'placement_records':len(plan),'active_records':8192,'edge_records':520,'edge_bias_connection':None,
         'route_policy':{'common':'M4 top-plate mesh; must avoid local M3-to-M5 lift landings',
                         'switched':'M3 bottom-plate row escapes; explicit isolated via3 outside CAPM and via4 to external M5 trunks',
                         'low_bits':'Retain short internal aggregation to center corridor then external M5; regenerate geometry from net groups and verified rules',
                         'original_3um_geometry_reused':False},
         'needed_before_numeric_generation':['Verified ordinary M3/M4/M5 and via3/via4 geometry/rules for selected school mapping, including actual via macros and cut/landing bbox',
            'Native routed 4um tile with separate common-M4 and switched-M3 exits; two adjacent different-bit units and a row end must pass DRC/LVS',
            'Model identity/port and multiplicity bridge from cap_mim_m3_1 to project p1_mim_public_r1: explicit instances or verified array multiplicity; current wrapper has no outer m',
            'Define device vs outside interconnect reference planes and CAPM coupling/ESR double-count policy from qualified evidence',
            'Actual substrate/edge bias top-level connectivity and target port mapping'],
         'stop_on_unknown':True,'formal_ADC_PEX_allowed':False})
    dump('verification.json',{'status':'LOCAL_READBACK_AND_MAPPING_PASS_PREPARATION_ONLY','native_GDS_shape_and_pin_match':True,
         'native_ADC_all_30_MIM_matches_export':True,'both_binary_banks_match':True,'unplaced_records_count':len(plan),
         'new_layout_generated':False,'new_DRC_LVS_PEX_run':False,'new_simulation_run':False,'formal_ADC_PEX_allowed':False})
    print('LOCAL_PREPARATION_PASS: actual 81-via native GDS, 30 ADC MIM, 8192 CDAC units; orientation mismatch retained; numerical pitch unresolved.')


if __name__=='__main__':
    main()
