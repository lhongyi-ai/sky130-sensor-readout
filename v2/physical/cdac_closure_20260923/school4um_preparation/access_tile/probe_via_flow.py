"""Read selected via rule numeric/branch metadata only, not full rule bodies."""
from pathlib import Path
import hashlib,json,re
root=Path('/opt/cadence/CDK/sky130_release_0.0.3')
out={'files':{}}
for basename in ['via3.drc.pvl','via4.drc.pvl','layer_def.drc.pvl']:
    p=root/'Sky130_DRC/Include'/basename;b=p.read_bytes();t=b.decode()
    t=re.sub(r'/\*.*?\*/','',t,flags=re.S);t=re.sub(r'//[^\n]*','',t)
    rec={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'selected_metadata':[]};out['files'][basename]=rec
    for n,s in enumerate(t.splitlines(),1):
        s=s.strip()
        if not s or re.match('caption',s,re.I):continue
        if basename=='layer_def.drc.pvl' and not re.search(r'areaid|\b(?:met[345]|via[34])\b',s,re.I):continue
        rec['selected_metadata'].append({'stripped_line':n,'tokens':re.findall(r'\$?[A-Za-z_][\w.]*',s),
          'numeric_values':re.findall(r'(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?![\w.])',s),
          'conditional':bool(re.search(r'if|define|else|endif',s,re.I))})
print(json.dumps(out,indent=2))
