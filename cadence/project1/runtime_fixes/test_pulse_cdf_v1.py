"""Audit repair inputs and native-netlist checks; this does not execute SKILL."""
import hashlib
import json
from pathlib import Path
import re
import sys

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'basic_design'))
from audit import check

MAPPING={'v1':'val0','v2':'val1','td':'delay','tr':'rise','tf':'fall','pw':'width','per':'period'}

def balance(text):
    depth=0;string=False;escape=False;comment=False
    for ch in text:
        if comment:
            if ch=='\n': comment=False
            continue
        if string:
            if escape: escape=False
            elif ch=='\\': escape=True
            elif ch=='"': string=False
            continue
        if ch==';': comment=True
        elif ch=='"': string=True
        elif ch=='(': depth+=1
        elif ch==')':
            depth-=1
            if depth<0: raise ValueError('Unmatched SKILL close')
    if string or depth: raise ValueError('Unbalanced SKILL')

def main(version='v1'):
    source=BASE/('releases/p1_fix_pulses_'+version+'.il')
    script=source.read_text();balance(script)
    targets=script.split('p1pTargets=list(',1)[1].split('procedure(p1pSameNumber',1)[0]
    fields=re.findall(r'list\("(v1|v2|td|tr|tf|pw|per)" "(\w+)" "([^"]+)"\)',targets)
    design=json.loads((BASE/'basic_design/design.json').read_text())
    pulses=[(cell,obj) for cell,data in design['cells'].items() for obj in data['instances'] if obj['cell']=='vpulse']
    assert [(cell,obj['name']) for cell,obj in pulses]==[('p1b_tb_rc','VIN'),('p1b_tb_step','VINP')]
    assert len(fields)==14
    for (cell,obj),block in zip(pulses,[fields[:7],fields[7:]]):
        assert 'list("'+cell+'" "'+obj['name']+'"' in targets
        assert {a:b for a,b,c in block}==MAPPING
        assert {b:c for a,b,c in block}==obj['props']
    # Local probe documents the shared analogLib names; the delivered script also
    # checks the actual vpulse instance CDF on Linux before writing anything.
    probe=(BASE/'reports/20260911_first_probe/cadence_report_share.txt').read_text()
    assert all('("analogLib" "vsource" "'+name+'"' in probe for name in MAPPING)
    bad=(BASE/'reports/basic_20260913T002329Z_b9bcf17f/received/runs/rc_step/20260913T002314Z_79b26ef4/native_netlist.scs').read_text()
    job=next(j for j in json.loads((BASE/'basic_design/jobs.json').read_text()) if j['id']=='rc_step')
    try: check(bad,design,job['cell'],job['params'])
    except ValueError as error: assert 'VIN.val1' in str(error)
    else: raise AssertionError('Broken source should fail')
    desired=dict(pulses[0][1]['props'])
    good=re.sub(r'^VIN .*$', 'VIN (VIN VSS) vsource type=pulse '+' '.join(k+'='+v for k,v in desired.items()),bad,flags=re.M)
    assert check(good,design,job['cell'],job['params'])['status']=='PASS'
    # Each altered value, not just the high voltage, must still be rejected.
    for name,value in desired.items():
        wrong=good.replace(name+'='+value+' ',name+'=999 ',1) if name!='period' else good.replace('period=10n','period=999')
        assert wrong!=good
        try: check(wrong,design,job['cell'],job['params'])
        except ValueError: pass
        else: raise AssertionError('Fault accepted: '+name)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    report=dict(status='PASS_LOCAL_STATIC_AND_NATIVE_AUDIT_CHECKS',skill_runtime='NOT_RUN',
        repair_file_sha256=digest,source_design_sha256=hashlib.sha256((BASE/'basic_design/design.json').read_bytes()).hexdigest(),
        affected_sources=2,parameters_checked=14,checks=['SKILL lexical balance','All frozen pulse sources covered with exact values',
        'CDF target names present in school analogLib source metadata',
        'Actual failed native RC netlist rejected','Correct native fixture accepted; seven altered pulse values rejected'])
    source.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n')
    source.with_suffix('.il.sha256').write_text(digest+'  '+source.name+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
