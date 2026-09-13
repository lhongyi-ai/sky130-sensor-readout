#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,sys,re
HERE=Path(__file__).resolve().parent
start=Path('/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice')
seen={};unresolved=[]
def visit(p):
 p=p.resolve()
 if str(p) in seen:return
 if not p.is_file():unresolved.append(str(p));return
 seen[str(p)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size}
 for line in p.read_text(errors='replace').splitlines():
  m=re.match(r'\s*\.(?:include|inc|lib)\s+[\"\']?([^\s\"\']+)',line,re.I)
  if m and ('.spice' in m[1] or '.lib' in m[1]):
   ref=Path(m[1]);visit(ref if ref.is_absolute() else p.parent/ref)
visit(start)
r=subprocess.run(['/foss/tools/ngspice/bin/ngspice','--version'],capture_output=True,text=True)
out={'python':sys.version,'simulator_version':r.stdout,'simulator_version_exit_code':r.returncode,'root_library':str(start),'referenced_model_files':seen,'unresolved_include_paths':unresolved,'container_name':'sky130-v2-resume-20260910','simulator_path':'/foss/tools/ngspice/bin/ngspice','SPICE_USERINIT_DIR':'/foss/pdks/sky130A/libs.tech/ngspice','school_paths_not_used':True}
(HERE/'environment.json').write_text(json.dumps(out,indent=2)+'\n');print('Model hashes:',len(seen),'unresolved:',len(unresolved))
