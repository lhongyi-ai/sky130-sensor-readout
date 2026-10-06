"""Bounded selected constraint metadata, not the school rule/technology body."""
from pathlib import Path
import collections,hashlib,json,re
r=Path('/opt/cadence/CDK/sky130_release_0.0.3')
p=r/'libs/sky130_fd_pr_main/techfile.tf';text=p.read_text();out={'technology_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'constraints':[],'via_defaults':[]}
for n,line in enumerate(text.splitlines(),1):
    s=line.split(';',1)[0].strip()
    if not re.search(r'\b(?:met[345]|via[34])\b',s):continue
    strings=re.findall(r'"([^"\n]*)"',s)
    plain=re.sub(r'"[^"\n]*"','',s)
    atoms=re.findall(r'[A-Za-z_][\w]*',plain)
    nums=re.findall(r'(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:e[-+]?\d+)?(?![\w.])',plain,re.I)
    if 1530<=n<=1670 and strings and nums:
        out['constraints'].append({'line':n,'operator':atoms[0] if atoms else None,'layers':strings[:2], 'reference_rule_id':strings[-1] if len(strings)>1 else None,'numeric_values':list(map(float,nums))})
    if 1360<=n<=1373:
        # Exact selected VIA3/VIA4 table has four lines; retain numbers only, with table schema comments below.
        out['via_defaults'].append({'line':n,'layer_names':[x for x in atoms if x in {'met3','met4','met5','via3','via4'}], 'quoted_names':strings,'numeric_values':list(map(float,nums))})
# Selected rule interface metadata from the standalone school DRC entry.
p=r/'Sky130_DRC/sky130_rev_0.0_1.0.drc.pvl';t=p.read_text();t=re.sub(r'/\*.*?\*/','',t,flags=re.S);t=re.sub(r'//[^\n]*','',t)
out['drc_token_histogram']=dict(collections.Counter((re.findall(r'[A-Za-z_][\w.]*',line) or [''])[0] for line in t.splitlines() if line.strip()))
out['drc_selected_checks']=[]
for n,line in enumerate(t.splitlines(),1):
    if not re.search(r'\b(?:met[345]|metal[345]|m[345]|via[34])\b',line,re.I):continue
    words=re.findall(r'[A-Za-z_][\w.]*',line);numbers=re.findall(r'(?<![\w.])\d+(?:\.\d*)?(?![\w.])',line)
    out['drc_selected_checks'].append({'stripped_line':n,'tokens':words,'numeric_values':numbers})
print(json.dumps(out,indent=2))
