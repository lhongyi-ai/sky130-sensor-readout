"""Selected include-file hashes and numerical-rule metadata only; no file body."""
from pathlib import Path
import hashlib,json,re
pdk=Path('/opt/cadence/CDK/sky130_release_0.0.3')
p=pdk/'Sky130_DRC/sky130_rev_0.0_1.0.drc.pvl';t=p.read_text();out={'files':[]}
for text in re.findall(r'(?mi)^\s*include\s+([^\n]+)',t):
    name=text.strip().strip('"')
    if Path(name).name not in {'m3.drc.pvl','m4.drc.pvl','m5.drc.pvl','via3.drc.pvl','via4.drc.pvl'}:continue
    # Existing executed project export_and_drc.sh explicitly sets this variable.
    resolved=name.replace('$PEGASUS_DRC',str(pdk/'Sky130_DRC'))
    q=Path(resolved);q=q if q.is_absolute() else p.parent/q
    record={'include_path':name,'resolved_path_relative_to_PDK':str(q.relative_to(pdk)),'exists':q.is_file()}
    if q.is_file():
        b=q.read_bytes();s=b.decode(errors='replace');record.update(sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
        s=re.sub(r'/\*.*?\*/','',s,flags=re.S);s=re.sub(r'//[^\n]*','',s)
        record['numeric_check_metadata']=[]
        for n,line in enumerate(s.splitlines(),1):
            if not re.search(r'\d',line) or not re.search(r'(width|space|external|internal|enclos|area|rectangle|length)',line,re.I):continue
            record['numeric_check_metadata'].append({'stripped_line':n,'operators_and_layers':re.findall(r'[A-Za-z_][\w.]*',line),'numeric_values':re.findall(r'(?<![\w.])[-+]?\d+(?:\.\d*)?(?![\w.])',line)})
    out['files'].append(record)
print(json.dumps(out,indent=2))
