"""Selected numerical contact metadata only. Never emit a technology file body."""
from pathlib import Path
import hashlib,json,re
root=Path('/opt/cadence/CDK/sky130_release_0.0.3')
drc=root/'Sky130_DRC/sky130_rev_0.0_1.0.drc.pvl';raw=drc.read_bytes()
p=root/'libs/sky130_fd_pr_main/techfile.tf';text=p.read_text()
sel=[]
for n,line in enumerate(text.splitlines(),1):
    s=line.split(';',1)[0].strip()
    if not s or not re.search(r'\b(?:met[345]|via[34])\b',s):continue
    strings=re.findall(r'"([^"\n]*)"',s)
    nums=re.findall(r'(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:e[-+]?\d+)?(?![\w.])',re.sub(r'"[^"\n]*"','',s),re.I)
    keyword=re.findall(r'\b(?:minWidth|minSpacing|minEnclosure|minExtension|minArea|via[34]|met[345])\b',s)
    # Metadata for only selected layers; structural syntax and other layers omitted.
    sel.append({'line':n,'selected_keywords':keyword,'quoted_names':strings,'numeric_values':nums})
out={'technology_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'technology_path_relative_to_PDK':str(p.relative_to(root)),
     'drc_readability':{'bytes':len(raw),'ascii_ratio':sum(x in (9,10,13) or 32<=x<=126 for x in raw)/len(raw),
          'encrypted_marker':bool(re.search(rb'encrypt',raw[:256],re.I)),'prefix_token':raw[:60].decode(errors='replace').split()[0]},
     'selected_technology_numeric_metadata':sel}
print(json.dumps(out,indent=2))
