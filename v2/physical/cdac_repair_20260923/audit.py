#!/usr/bin/env python3
"""Independent graph/charge audit. No layout generation and no simulator calls.

Reads frozen inputs; writes only this new directory. Uses a BFS connected-
component implementation and Decimal edge summation independent of the old
union-find analyzer. Counterfactual weights are diagnostic, not new PEX.
"""
import csv
from collections import Counter, defaultdict, deque
from decimal import Decimal, getcontext
import hashlib
import json
from pathlib import Path
import re

getcontext().prec = 42
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ROUTE = HERE.parent / 'cdac_route_20260911'
UNIT = Decimal('19.845')  # fF, frozen open-PDK TT unit evidence
SCALE = {'':Decimal('1e15'), 'f':Decimal(1), 'p':Decimal(1000),
         'n':Decimal('1e6'), 'u':Decimal('1e9'), 'm':Decimal('1e12'),
         'k':Decimal('1e18'), 'meg':Decimal('1e21')}

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def number_ff(s):
    m = re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([a-z]*)', s)
    if not m or m[2] not in SCALE:
        raise ValueError('Unsupported number: '+s)
    return Decimal(m[1])*SCALE[m[2]]

def parse(path):
    records=[]; ports=[]; header=False
    for line in path.read_text().splitlines():
        t=line.split()
        if not t or t[0].startswith('*'): continue
        if t[0].lower()=='.subckt': ports=t[2:]; header=True; continue
        if t[0]=='+':
            if not header: raise ValueError('Unexpected continuation')
            ports.extend(t[1:]); continue
        header=False
        if t[0][0].upper() in 'RCX': records.append(t)
    assert len(set(t[0] for t in records))==len(records), 'Duplicate element IDs'
    adjacency=defaultdict(set); allnodes=set(ports)|{'VSUBS'}
    for t in records:
        allnodes.update(t[1:3])
        if t[0][0].upper()=='R':
            assert len(t)==4 and Decimal(t[3])>0
            adjacency[t[1]].add(t[2]); adjacency[t[2]].add(t[1])
    labels={}; components=[]; declared=set(ports)|{'VSUBS'}
    for first in sorted(allnodes):
        if first in labels: continue
        pending=deque([first]); seen={first}
        while pending:
            n=pending.popleft()
            for nb in adjacency[n]:
                if nb not in seen: seen.add(nb); pending.append(nb)
        names=seen&declared
        assert len(names)==1, ('Unbound or shorted component',sorted(names))
        name=next(iter(names))
        for n in seen: labels[n]=name
        components.append(sorted(seen))
    parasitic=defaultdict(Decimal); intrinsic=defaultdict(Decimal)
    edge_items=defaultdict(list); count=Counter(); excluded=defaultdict(Decimal)
    for t in records:
        kind=t[0][0].upper(); count[kind]+=1
        if kind=='R': continue
        if kind=='C':
            assert len(t)==4
            value=number_ff(t[3]); assert value>=0
        else:
            assert t[3]=='sky130_fd_pr__cap_mim_m3_1'
            assert set(t[4:])=={'l=3','w=3'}
            value=UNIT
        a,b=labels[t[1]],labels[t[2]]
        if a==b:
            excluded[kind]+=value; count[kind+'_self_loop']+=1; continue
        pair=tuple(sorted((a,b)))
        (parasitic if kind=='C' else intrinsic)[pair]+=value
        edge_items[pair].append((t[0],str(value)))
    nodes=sorted(declared); index={n:i for i,n in enumerate(nodes)}
    mat=[[Decimal(0) for _ in nodes] for _ in nodes]
    for pair in set(parasitic)|set(intrinsic):
        a,b=map(index.get,pair); c=parasitic[pair]+intrinsic[pair]
        mat[a][a]+=c; mat[b][b]+=c; mat[a][b]-=c; mat[b][a]-=c
    assert all(sum(r)==0 for r in mat), 'Charge conservation violated'
    assert all(mat[i][j]==mat[j][i] for i in range(len(nodes)) for j in range(len(nodes)))
    assert all(mat[i][i]>=0 and all(mat[i][j]<=0 for j in range(len(nodes)) if i!=j) for i in range(len(nodes)))
    return dict(ports=ports,parasitic=parasitic,intrinsic=intrinsic,counts=dict(count),
                excluded_ff={k:str(v) for k,v in excluded.items()},matrix=mat,nodes=nodes,
                components=len(components),edge_items=edge_items)

def pair(net,a,b,which='parasitic'):
    return net[which].get(tuple(sorted((a,b))),Decimal(0))

def metrics(weights):
    span=sum(weights); lsb=span/Decimal(4095)
    codes=[sum((weights[i] for i in range(12) if code&(1<<i)),Decimal(0)) for code in range(4096)]
    inl=[v/lsb-Decimal(i) for i,v in enumerate(codes)]
    dnl=[(codes[i+1]-codes[i])/lsb-1 for i in range(4095)]
    return dict(max_abs_inl_lsb=float(max(map(abs,inl))),min_dnl_lsb=float(min(dnl)),
                max_dnl_lsb=float(max(dnl)),nonpositive_transition_count=sum(x<=-1 for x in dnl),
                pass_static_limits=max(map(abs,inl))<=Decimal('1.5') and min(dnl)>=Decimal('-.9') and max(dnl)<=Decimal('1.5'))

def write_csv(name,rows):
    with (HERE/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    top_path=ROUTE/'artifacts/cdac_diff_routed_flat_rc.spice'
    top=parse(top_path); sources={str(top_path.relative_to(ROOT)):digest(top_path)}
    device_path=ROOT/'v2/environment/results/device_qualification.json'
    device_evidence=json.loads(device_path.read_text())
    nominal=[r for r in device_evidence['runs'] if r['name']=='pvt/tt_1.80_27' and r['corner']=='tt']
    assert device_evidence['status']=='OPEN_DEVICE_ENVIRONMENT_PASS' and len(nominal)==1
    assert abs(Decimal(str(nominal[0]['cap_a']))*Decimal('1e15')-UNIT)<Decimal('1e-10')
    for p in (device_path, ROUTE/'generate_routed_cdac.py',
              ROOT/'v2/analog/adc/cdac_pex_linearity_20260911/qualification.json'):
        sources[str(p.relative_to(ROOT))]=digest(p)
    totals={s:sum(top['matrix'][top['nodes'].index(s+'_TOP')][j]*(-1)
                         for j,n in enumerate(top['nodes']) if n!=s+'_TOP') for s in ('P','N')}
    assert pair(top,'P_TOP','N_TOP')==0 and pair(top,'P_TOP','N_TOP','intrinsic')==0
    rows=[]; carry=[]; cap_checks=[]; originals=[]; revised=[]
    for side in ('P','N'):
        cap_path=ROUTE/f'artifacts/cdac_side_{side.lower()}_routed_flat.cap.spice'
        cap=parse(cap_path); sources[str(cap_path.relative_to(ROOT))]=digest(cap_path)
        # The cap-only view predates extresist; it independently retains the same issue.
        diffs=[abs(pair(top,side+'_TOP',side+'_B'+str(i))-pair(cap,'TOP','B'+str(i))) for i in range(12)]
        cap_checks.append(dict(side=side,max_cap_only_vs_rc_top_bit_difference_ff=float(max(diffs)),
                               all_12_couplings_exactly_equal=all(d==0 for d in diffs),
                               interpretation='Both views contain the same low-bit excess before and after RC subdivision'))
        slope=pair(top,side+'_TOP',side+'_B8')/Decimal(256)
        ow=[]; rw=[]
        for i in range(12):
            p=pair(top,side+'_TOP',side+'_B'+str(i));intr=pair(top,side+'_TOP',side+'_B'+str(i),'intrinsic')
            assert intr==UNIT*(1<<i)
            excess=p-slope*(1<<i)
            ow.append(intr+p);rw.append(intr+(slope*(1<<i) if i<=5 else p))
            rows.append(dict(side=side,bit=i,units=1<<i,intrinsic_ff=str(intr),parasitic_ff=str(p),
                        parasitic_per_unit_ff=str(p/Decimal(1<<i)),high_bit_slope_ff=str(slope),
                        excess_vs_proportional_ff=str(excess),
                        proposed_removal_diagnostic_only_ff=str(excess if i<=5 else Decimal(0))))
        originals.append(ow);revised.append(rw)
    weights=[sum(originals[j][i]/totals[s] for j,s in enumerate(('P','N'))) for i in range(12)]
    revised_totals={s:totals[s]-sum(originals[j])+sum(revised[j]) for j,s in enumerate(('P','N'))}
    fixed=[sum(revised[j][i]/revised_totals[s] for j,s in enumerate(('P','N'))) for i in range(12)]
    lsb=sum(weights)/Decimal(4095)
    for i in range(12):
        step=weights[i]-sum(weights[:i]);carry.append(dict(rising_bit=i,first_from_code=(1<<i)-1,
               transition_occurrences=1<<(11-i),step_in_endpoint_lsb=str(step/lsb),dnl_lsb=str(step/lsb-1),nonpositive=step<=0))
    write_csv('top_bit_coupling_budget.csv',rows);write_csv('carry_diagnosis.csv',carry)
    previous=json.loads((ROOT/'v2/analog/adc/cdac_pex_linearity_20260911/qualification.json').read_text())
    actual=metrics(weights)
    for key in ('max_abs_inl_lsb','min_dnl_lsb','max_dnl_lsb'):
        assert abs(actual[key]-previous['results']['differential'][key])<1e-8
    assert actual['nonpositive_transition_count']==255
    report=dict(status='INDEPENDENT_GRAPH_AUDIT_COMPLETE_PHYSICAL_REPAIR_NOT_RUN',
       source_sha256=sources,unit_capacitance_ff=str(UNIT),unit_scope='Existing open PDK 3x3 only; not school 4x4',
       graph=dict(components=top['components'],ports=len(top['ports']),counts=top['counts'],
                  excluded_self_loop_capacitance_ff=top['excluded_ff'],
                  all_components_reach_exactly_one_port_or_substrate=True,duplicate_element_ids=False,
                  symmetric_matrix=True,charge_conservation_row_sums_zero=True,
                  all_nonnegative_capacitor_edges=True,cross_side_top_coupling_zero=True),
       original_static=actual,cap_only_independent_checks=cap_checks,
       counterfactual=dict(scope='Sensitivity calculation only. Remove lower-bit excess vs B8 per-unit slope; no new layout or PEX.',
                           apparent_static=metrics(fixed),physical_implementation_validated=False),
       mechanism='Non-proportional TOP-to-small-bit capacitance exists before RC subdivision. Internal low-bit M5 trunks cross TOP, whereas high-bit trunks are outside array. This is a leading physical hypothesis, not an isolated geometry experiment.',
       school_gate='School CDF reportedly minimum 4x4: preserve old 3x3 evidence, obtain actual school unit geometry/model before new native layout.',
       full_adc_pass=False,layout_repair_pass=False)
    (HERE/'diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],original=actual,counterfactual=report['counterfactual']['apparent_static'],cap_only_checks=cap_checks),indent=2))

if __name__=='__main__': main()
