#!/usr/bin/env python3
"""Fail-closed readiness check. Does not simulate or award performance signoff."""
import argparse,json
from pathlib import Path
from prepare import ROOT,HERE,sha,rc_counts,subckt
REQUIRED={'cdac','sampling_switch','digital','frontend','comparator_and_preamp','reference_selection_and_distribution','nonoverlap_phase_and_clock_drive','core_interconnect_and_power_routing'}

def evaluate(bindings,root=ROOT):
    reasons=[]
    def require(condition,reason):
        if not condition:reasons.append(reason)
    require(bool(bindings.get('frozen_source_sha256')),'source hash map missing')
    for rel,h in bindings.get('frozen_source_sha256',{}).items():
        p=root/rel;require(p.is_file() and sha(p)==h,'missing or stale source: '+rel)
    require(not bindings.get('missing_required_views'),'required physical views are missing: '+', '.join(bindings.get('missing_required_views',[])))
    require(REQUIRED.issubset(bindings.get('bindings',{})),'full core module inventory incomplete')
    for name,b in bindings.get('bindings',{}).items():
        for field in ['view','gds']+(['bound_view'] if 'bound_view' in b else []):
            p=root/b.get(field,'__missing__');require(p.is_file() and b.get(field+'_sha256')==sha(p),'missing or stale '+name+' '+field)
        if b.get('view_kind')=='analog_extracted_rc':
            p=root/b.get('view','__missing__')
            if p.is_file():
                counts=rc_counts(p);require(counts['positive_resistors']>0 and counts['positive_capacitors']>0,'unextracted analog view: '+name)
                try:require(subckt(p,b['subckt'])==b['pins'],'port mismatch: '+name)
                except (ValueError,KeyError):reasons.append('invalid subcircuit binding: '+name)
        elif name=='digital':
            require(b.get('view_kind') in ['gate_spef_sdf_qualified','transistor_extracted_rc_qualified'],'digital LVS-only SPICE is not a post-layout simulation view')
    top=bindings.get('full_core_extracted_view')
    require(isinstance(top,dict),'full core extracted view missing')
    if isinstance(top,dict):
        require(top.get('contains_top_level_interconnect_rc') is True,'full core routing parasitics not extracted')
        for field in ['gds','schematic','pex','drc_report','lvs_report']:
            p=root/top.get(field,'__missing__');require(p.is_file() and top.get(field+'_sha256')==sha(p),'missing or stale full core '+field)
        p=root/top.get('pex','__missing__')
        if p.is_file():
            counts=rc_counts(p);require(counts['positive_resistors']>0 and counts['positive_capacitors']>0,'full core PEX has no positive R/C')
        require(top.get('drc_errors')==0,'full core DRC not closed')
        require(top.get('lvs_unique_match') is True,'full core LVS not closed')
        p=root/top.get('lvs_report','__missing__')
        if p.is_file():require('Circuits match uniquely' in p.read_text(),'full core raw LVS lacks unique match')
    # Performance remains independent: readiness PASS never grants chip acceptance.
    return {'status':'READY_FOR_FULL_CORE_POSTLAYOUT_SIMULATION' if not reasons else 'BLOCKED_FULL_CORE_POSTLAYOUT','ready_to_simulate':not reasons,'full_core_performance_pass':False,'reasons':reasons,'scope':'Readiness and binding integrity only; the 135-row performance matrix must be executed and independently evaluated.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bindings',type=Path,default=HERE/'extracted_view_bindings.json');args=parser.parse_args()
    result=evaluate(json.loads(args.bindings.read_text()));(HERE/'postlayout_readiness.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return 0 if result['ready_to_simulate'] else 2
if __name__=='__main__':raise SystemExit(main())
