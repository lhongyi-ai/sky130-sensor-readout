"""Bounded entry/include graph metadata for via3/CAPM exclusions and Copper flag."""
from pathlib import Path
import hashlib,json,re
root=Path('/opt/cadence/CDK/sky130_release_0.0.3/Sky130_DRC')
entry=root/'sky130_rev_0.0_1.0.drc.pvl'
def clean(text):
    return re.sub(r'//[^\n]*','',re.sub(r'/\*.*?\*/','',text,flags=re.S))
out={'scope':'Entry plus its 41 explicit includes; selected interfaces/conditionals only','files':[],'via3_definitions_or_modifications':[], 'capm_via3_cooccurrences':[],'preprocessor':[]}
queue=[entry];seen=set()
while queue:
    p=queue.pop(0)
    if p in seen:continue
    seen.add(p);assert root in p.parents
    b=p.read_bytes();t=clean(b.decode());out['files'].append({'name':str(p.relative_to(root)),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
    for inc in re.findall(r'(?mi)^\s*include\s+([^\n]+)',t):
        inc=inc.strip().strip('"')
        q=Path(inc.replace('$PEGASUS_DRC',str(root)));q=q if q.is_absolute() else p.parent/q
        queue.append(q)
    for n,line in enumerate(t.splitlines(),1):
        tokens=re.findall(r'\$?[A-Za-z_][\w.]*',line)
        nums=re.findall(r'(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?![\w.])',line)
        m={'file':str(p.relative_to(root)),'stripped_line':n,'tokens':tokens,'numeric_values':nums}
        if re.search(r'(?:#\s*)?\b(?:IFDEF|IFNDEF|DEFINE|UNDEF|ELSE|ENDIF)\b',line,re.I) and ('Copper' in tokens or p==entry):out['preprocessor'].append(m)
        if re.search(r'\blayer_def\s+via3\b|\boutputlayer\s+via3\s*(?:$|[;}])|\bvia3\s*=',line,re.I):out['via3_definitions_or_modifications'].append(m)
        if re.search(r'\bcapm\b',line,re.I) and re.search(r'\bvia3\b',line,re.I):out['capm_via3_cooccurrences'].append(m)
    if p.name=='layer_def.drc.pvl':
        defs={name:target for name,target in re.findall(r'\blayer_def\s+(\S+)\s+(\d+)',t)}
        for name in ['via3','areaid.mt','capm']:
            target=defs[name];maps=re.findall(r'\blayer_map\s+(\d+)\s+-(datatype|texttype)\s+(\d+)\s+'+target+r'\b',t)
            out[name+'_input_maps']=[{'gds':[int(g),int(d)],'type':typ} for g,typ,d in maps]
print(json.dumps(out,indent=2))
