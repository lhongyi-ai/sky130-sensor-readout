"""SSH stdin read-only probe. Emit selected interface metadata, not rule source."""
from pathlib import Path
import hashlib,json,re
root=Path('/opt/cadence/CDK/sky130_release_0.0.3')
paths={'stream':root/'libs/sky130_fd_pr_main/sky130_fd_pr_main.layermap',
       'drc':root/'Sky130_DRC/sky130_rev_0.0_1.0.drc.pvl',
       'lvs':root/'Sky130_LVS/Sky130_rev_0.0_0.1.lvs.pvl'}
out={'scope':'READ_ONLY_SELECTED_LAYER_AND_RULE_METADATA','files':{},'stream':[],'pvs_maps':{}}
for kind,p in paths.items():
    raw=p.read_bytes();t=raw.decode(errors='replace')
    out['files'][kind]={'path_relative_to_PDK':str(p.relative_to(root)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if kind=='stream':
        for line in t.splitlines():
            a=line.split()
            if len(a)>=4 and a[0] in {'met3','met4','met5','via3','via4','capm'} and a[2].isdigit() and a[3].isdigit():
                out['stream'].append({'name':a[0],'purpose':a[1],'gds':[int(a[2]),int(a[3])]})
    else:
        t=re.sub(r'/\*.*?\*/','',t,flags=re.S);t=re.sub(r'//[^\n]*','',t)
        defs={int(i):name for name,i in re.findall(r'\blayer_def\s+(\w+)\s+(\d+)',t)}
        sel=[]
        for gds,typ,dt,target in re.findall(r'\blayer_map\s+(\d+)\s+-(datatype|texttype)\s+(\d+)\s+(\d+)',t):
            name=defs.get(int(target),'')
            if re.search(r'^(met(al)?[345]|via[34]|capm)(_|$)',name,re.I):
                sel.append({'name':name,'gds':[int(gds),int(dt)],'type':typ})
        out['pvs_maps'][kind]=sel
        if kind=='drc':
            out['relevant_rule_names']=re.findall(r'(?m)^\s*([\w.]+)\s*\{',t)
            out['relevant_rule_names']=[n for n in out['relevant_rule_names'] if re.search(r'(via[34]|met[345]|metal[345])',n,re.I)]
print(json.dumps(out,indent=2))
