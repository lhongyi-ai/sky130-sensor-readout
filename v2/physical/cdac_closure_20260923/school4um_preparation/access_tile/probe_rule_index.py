"""Read-only file index and rule-name discovery; no rule source output."""
from pathlib import Path
import hashlib,json,re
pdk=Path('/opt/cadence/CDK/sky130_release_0.0.3')
p=pdk/'Sky130_DRC/sky130_rev_0.0_1.0.drc.pvl';t=p.read_text()
o={'entry_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
   'include_paths':re.findall(r'(?m)^\s*(?:#include|include)\s+([^\n]+)',t),
   'rule_names':re.findall(r'(?m)^\s*(?:rule|check)\s+([^\n{]+)',t),
   'rule_directory_files':[x.name for x in p.parent.iterdir() if x.is_file()],
   'primitive_library_top_files':[x.name for x in (pdk/'libs/sky130_fd_pr_main').iterdir() if x.is_file()]}
print(json.dumps(o,indent=2))
