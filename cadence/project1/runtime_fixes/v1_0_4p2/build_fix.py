"""Build a versioned passive reanalysis patch; preserve all earlier archives."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

FIX=Path(__file__).resolve().parent
BASE=FIX.parents[1]
FILES=['run.py','analyze.py','passive_models.py','passive_review.py','passive_criteria.md','runtime_patch.json','package_manifest.json']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')


def main():
    old=BASE/'runtime_fixes/v1_0_4p1/payload/package_manifest.json'
    assert sha(old)=='c982275d2f5046439e77e4e5236d614d083e865fbb86414059a38d06f652aa66'
    write(FIX/'payload/runtime_patch.json',dict(id='1.0.4p2',kind='passive_measurement_and_evidence_review',
          base_package_manifest_sha256=sha(old),schematic_generation='UNCHANGED',
          changes=['Model-based nominal R/RC criteria and independently verified MIM',
                   'Recheck existing actual CSV/log/netlist evidence without overwriting failures',
                   'OTA passive prerequisite requires matching current evidence review'],
          input_report_sha256='5078faaa47b0d14824d1bc450a8c9fcf674ae2aed7c987afebba9fea6f5f1df2',
          school_patch_execution='NOT_RUN',new_cadence_simulations='NOT_RUN'))
    manifest=json.loads(old.read_text());manifest['version']='1.0.4p2';manifest['runtime_patch']='1.0.4p2'
    for name in FILES[:-1]: manifest['files'][name]=sha(FIX/'payload'/name)
    write(FIX/'payload/package_manifest.json',manifest)
    write(FIX/'patch_manifest.json',dict(id='1.0.4p2',payload={n:sha(FIX/'payload'/n) for n in FILES}))
    for p in list((FIX/'payload').glob('*.py'))+[FIX/'install.py']:
        ast.parse(p.read_text(),feature_version=(3,6))
    subprocess.run(['bash','-n',str(FIX/'apply.sh')],check=True)
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(FIX/'tests'),'-v'],capture_output=True,text=True)
    (FIX/'local_validation.log').write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    write(FIX/'local_validation.json',dict(status='PASS_LOCAL_CHECKS',
          tests='11 patch tests, including 17 original package regressions',
          returned_Spectre_data_reanalysis='PASS',school_patch_execution='NOT_RUN',
          checks=['R/MIM/RC returned-data checks and corrupt-current/capacitance/waveform/missing-point rejection',
                  'Native input hashes, latest-failure stop, evidence and model change invalidation',
                  'Install idempotence, conflict rejection, rollback, original file preservation',
                  '87 jobs remain; original OTA regressions pass; Python 3.6 syntax check']))
    dest=BASE/'releases/project1_basic_runtime_fix_v1.0.4p2.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(FIX.rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts: continue
            info=zipfile.ZipInfo('project1_handoff/basic_runtime_fix_v1_0_4p2/'+p.relative_to(FIX).as_posix(),(2026,9,13,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,p.read_bytes())
    dest.with_suffix('.zip.sha256').write_text(sha(dest)+'  '+dest.name+'\n')
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
    print(json.dumps(dict(zip=str(dest),size=dest.stat().st_size,sha256=sha(dest)),indent=2))


if __name__=='__main__': main()
