#!/usr/bin/env python3
"""Re-read real school artifacts; no CAD execution or source/result rewriting."""
from pathlib import Path
import collections,hashlib,importlib.util,json,re,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
EVIDENCE=ROOT/'v2/analog/adc/cadence_closure_20260923/runs/task_20260924T071455411070Z/tile'
RUN=EVIDENCE/'runs/access_first'
s=importlib.util.spec_from_file_location('school4prep',HERE.parent/'prepare.py')
prep=importlib.util.module_from_spec(s);s.loader.exec_module(prep)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    originals=['create_access_tiles.il','control_geometry.json','access.map','good.cdl','open.cdl','short.cdl',
               'rules/mim_layers.pvl','rules/mim_lvs.pvl','rules/mim_drc.pvl']
    for rel in originals:assert sha(HERE/rel)==sha(EVIDENCE/rel),('executed input mismatch',rel)
    cases=json.loads((HERE/'control_geometry.json').read_text())['cases']
    summary=json.loads((RUN/'summary.json').read_text())
    layers={'met3':(70,20),'met4':(71,20),'met5':(72,20),'via3':(70,44),'via4':(71,44),'capm':(89,44)}
    report={'status':'SCOPED_2X2_SHARED_ACCESS_GEOMETRY_AND_LVS_VERIFIED','source_run':str(RUN.relative_to(ROOT)),
            'actual_execution_by':'root task on school LinuxLab','review_execution':'local artifact readback only','cases':{},
            'formal_ADC_PEX_allowed':False,'PEX':'NOT_RUN','electrical_performance':'NOT_RUN','full_array_pitch_qualified':False}
    files=[RUN/'summary.json']+[EVIDENCE/x for x in originals]
    for key,case in cases.items():
        p=RUN/key;cell=case['cell'];rr={'cell':cell};report['cases'][key]=rr
        names,dbu,items=prep.flat_gds(p/'layout.gds');assert names==[cell]
        actual=collections.Counter((e['layer'],e['datatype'],tuple(prep.bbox(e['points_um']))) for e in items if e['kind']=='polygon' and e['datatype']!=16)
        expected=collections.Counter((*layers[r['layer']],tuple(r['bbox_um'])) for r in case['shapes'])
        assert actual==expected
        texts={e['text']:e for e in items if e['kind']=='text'}
        assert set(texts)=={'TOP','B00','B01','B10','B11'}
        for name,layer,point in case['pins']:
            e=texts[name];assert e['layer']==layers[layer][0] and e['datatype']==5 and e['points_um']==[point]
        assert sha(p/'layout.gds')==summary['cases'][key]['gds_sha256']
        rr['native_GDS']={'status':'ALL_DRAWING_RECTANGLES_AND_LABELS_MATCH','drawing_rectangle_count':sum(actual.values()),
                         'via3_cut_count':sum(e['kind']=='polygon' and (e['layer'],e['datatype'])==(70,44) for e in items),
                         'via4_cut_count':sum(e['kind']=='polygon' and (e['layer'],e['datatype'])==(71,44) for e in items),
                         'CAPM_count':sum(e['kind']=='polygon' and (e['layer'],e['datatype'])==(89,44) for e in items)}
        files += [p/'layout.gds',p/'stream.log',p/'stream.sum']
        for kind,nchecks,sumname in [('school_drc',279,'sky130_fd_sc_ls__bufinv_16.sum'),('mim_drc',9,'result.sum')]:
            d=p/kind;sm=(d/sumname).read_text();log=(d/'pvs.log').read_text(errors='replace');ascii=(d/'errors.ascii').read_text()
            assert re.search(r'Layout Primary Cell\s*:\s*'+re.escape(cell)+r'\s*$',sm,re.M)
            assert '/'+key+'/layout.gds' in sm
            assert ascii.splitlines()[0].split()[0]==cell
            assert int(re.search(r'(?m)^Total DRC RuleChecks\s*:\s*(\d+)',sm)[1])==nchecks
            assert int(re.search(r'(?m)^Total DRC Results\s*:\s*(\d+)',sm)[1])==0
            completed=re.findall(r'Rule Check (\S+) finished, (\d+) error\(s\) reported',log)
            assert len(completed)==nchecks and len(dict(completed))==nchecks and all(v=='0' for n,v in completed)
            counts=re.findall(r'(?m)^([^\s"].*)\n(\d+)\s+(\d+)\s+\d+\s+[A-Z][a-z]{2}\s',ascii)
            assert len(counts)==nchecks and all(a==b=='0' for n,a,b in counts)
            assert {n for n,a,b in counts}=={n for n,v in completed}
            assert 'Checking out SoftShare license Pegasus_DRC 21.1 Qty: 1 ... succeeded' in log
            # Per-layer entries also contain this phrase; match only the top-level total.
            geometry=int(re.search(r'(?m)^Total Original Geometry\s*:\s*(\d+)',sm)[1])
            assert geometry==({'good':364,'open':363,'short':365} if kind=='school_drc' else {'good':356,'open':355,'short':357})[key]
            rr[kind]={'result':'ZERO_RESULTS_FOR_EXECUTED_CHECKS','checks':nchecks,'results':0,'summary_log_ascii_agree':True,'actual_top_and_GDS_confirmed':True,
                       'tool_original_geometry_count':geometry,'initial_XL_license_unavailable':bool(re.search(r'License call failed for feature Phys_Ver_Sys_DRC_XL',log)),
                       'Pegasus_DRC_license_checkout_succeeded':True}
            if kind=='school_drc':
                relevant={n:int(v) for n,v in completed if re.match(r'(?:m[345]\.|via[34]\.)',n)}
                assert 'via3.4' in relevant and 'm5.3' in relevant and 'via3.11' not in relevant and 'via4.4' not in relevant
                rr[kind]['selected_executed_rules']=relevant
                rr[kind]['observed_branch']='non-Copper, confirmed by executed rule IDs; areaid.mt marker not added'
                rr[kind]['coverage_limits']=['via4.4 M4 enclosure check belongs to unexecuted Copper branch; drawn enclosure is checked geometrically, not claimed as active rule coverage',
                    'via3.1 0.2 size check selects areaid.mt; no areaid.mt in this GDS. A zero result is not proof that outside-region cut size was checked',
                    'No new intentionally undersized metal/via DRC counterexample in this run; open/short are connectivity controls']
            files += [d/sumname,d/'pvs.log',d/'errors.ascii',d/'pvs.argv.json']
        d=p/'lvs';sp=(d/'extracted.spice').read_text();cls=(d/(cell+'.lvsrpt.cls')).read_text();ext=(d/(cell+'.lvsrpt')).read_text();log=(d/'pvs.log').read_text()
        assert sha(d/'source.cdl')==sha(HERE/(key+'.cdl'))
        for fn in ['mim_layers.pvl','mim_lvs.pvl']:assert sha(d/fn)==sha(HERE/'rules'/fn)
        match=re.search(r'Run Result\s*:\s*(\S+)',cls)[1]
        assert match==('MATCH' if key=='good' else 'MISMATCH')
        assert int(re.search(r'Cells that have been blackboxed\s*\|\s*(\d+)',cls)[1])==0
        assert int(re.search(r'Cells not run\s*\|\s*(\d+)',cls)[1])==0
        sub=re.search(r'(?mi)^\.subckt\s+'+re.escape(cell)+r'\s+([^\n]+)',sp)[1].split()
        n,ep,fdc=map(int,re.search(r'\*\* N=(\d+) EP=(\d+) FDC=(\d+)',sp).groups())
        dev=re.findall(r'(?m)^(X\S+)\s+(\S+)\s+(\S+)\s+p1_mim_public_r1\s+w=(\S+)\s+l=(\S+)\s+\$X=(-?\d+)\s+\$Y=(-?\d+)',sp)
        assert len(dev)==fdc==4 and all(float(w)==float(l)==4e-6 for name,a,b,w,l,x,y in dev)
        locations={(int(x),int(y)):(a,b) for name,a,b,w,l,x,y in dev}
        assert set(locations)=={(0,0),(0,12000),(12000,0),(12000,12000)}
        terms=[(a,b) for name,a,b,w,l,x,y in dev]
        expected_bottoms={(0,0):'B00',(12000,0):'B01',(0,12000):'B10',(12000,12000):'B11'}
        if key=='good':
            assert set(sub)=={'TOP','B00','B01','B10','B11'} and (n,ep)==(5,5)
            assert all(locations[xy]==('TOP',b) for xy,b in expected_bottoms.items())
        elif key=='open':
            assert set(sub)=={'TOP','B00','B01','B10','B11'} and (n,ep)==(6,5)
            floating=locations[(0,0)][0]
            assert floating not in sub and locations[(12000,0)][0]==floating
            assert locations[(0,12000)][0]==locations[(12000,12000)][0]=='TOP'
            assert all(locations[xy][1]==b for xy,b in expected_bottoms.items())
        else:
            assert set(sub)=={'TOP','B00','B01','B11'} and (n,ep)==(4,4)
            assert all(locations[xy]==('TOP','B00' if b=='B10' else b) for xy,b in expected_bottoms.items())
            assert 'Different labels for net' in ext and 'Label "B00"' in ext and 'Label "B10"' in ext
        assert 'Checking out SoftShare license Pegasus_LVS 21.1 Qty: 1 ... succeeded' in log
        rr['LVS']={'result':match,'matches_expected':True,'blackboxes':0,'cells_not_run':0,'MIM_device_count':4,'dimensions_um':[4,4],
                   'layout_ports':sub,'source_ports':['TOP','B00','B01','B10','B11'],'layout_net_count':n,'layout_external_port_count':ep,
                   'device_terminals_PLUS_MINUS':terms,'source_and_project_rules_match_frozen_input':True,'Pegasus_LVS_checkout_succeeded':True,
                   'device_coordinates_PVS_dbu':[{ 'xy':list(xy),'PLUS_MINUS':list(nodes)} for xy,nodes in sorted(locations.items())],
                   'failure_explanation':None if key=='good' else 'Lower-row two PLUS terminals share floating internal node '+floating+'; upper row remains TOP' if key=='open' else 'Left-column B00/B10 physically merge; layout has 4 ports vs source 5',
                   'parallel_reduction_used_to_hide_error':False}
        files += [d/'source.cdl',d/'extracted.spice',d/(cell+'.lvsrpt'),d/(cell+'.lvsrpt.cls'),d/'pvs.log',d/'pvs.argv.json',d/'mim_layers.pvl',d/'mim_lvs.pvl']
    report['scoped_acceptance']='Actual 2x2 four-device 4um shared-top access control and its cross-row open/short LVS controls accepted; no geometry repair needed for these inputs.'
    report['not_proven']=['All geometric rule coverage','Complete CDAC layout or final pitch','Statistical/device-model equivalence','CAPM coupling/RC reference planes','PEX accuracy or ADC performance']
    report['parser_revision']={'version':2,'reason':'Anchor top-level Original Geometry summary; initial v1 matched first per-layer count. Actual GDS, completed-rule, ASCII and LVS checks unchanged; no CAD rerun.',
                               'initial_report_preserved_in':'review_parser_history_v1/'}
    (HERE/'actual_execution_review.json').write_text(json.dumps(report,indent=2)+'\n')
    manifest={str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in files}
    (HERE/'actual_evidence_manifest.json').write_text(json.dumps({'private_original_artifacts':True,'do_not_publish_expanded_school_rule_logs':True,'files':manifest},indent=2)+'\n')
    status=json.loads((HERE/'preparation_status.json').read_text())
    status['initial_preparation_status']='PREPARED_NOT_RUN';status['status']=report['status'];status['native_cell_creation']='ACTUALLY_EXECUTED_BY_ROOT'
    status['DRC']='ZERO_RESULTS_FOR_EXECUTED_SCHOOL_279_AND_MIM_9_CHECKS_EACH_CASE';status['LVS']='GOOD_MATCH_OPEN_AND_SHORT_MISMATCH_VERIFIED'
    status['actual_review']='actual_execution_review.json';status['geometry_repair_required_for_this_tile']=False
    (HERE/'preparation_status.json').write_text(json.dumps(status,indent=2)+'\n')
    print('SCOPED_2X2_SHARED_ACCESS_GEOMETRY_AND_LVS_VERIFIED: 3 actual GDS; 279+9 DRC each; 4 MIM each; good MATCH, open/short MISMATCH. PEX NOT_RUN.')

if __name__=='__main__':main()
