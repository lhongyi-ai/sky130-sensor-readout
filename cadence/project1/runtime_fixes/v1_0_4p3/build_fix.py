"""Build the OP export correction without overwriting earlier releases."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

FIX=Path(__file__).resolve().parent;BASE=FIX.parents[1]
FILES=['run.py','analyze.py','passive_review.py','runtime_patch.json','package_manifest.json']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')


def main():
    old=BASE/'runtime_fixes/v1_0_4p2/payload/package_manifest.json'
    assert sha(old)=='3502851b9bacef25d0c2e9f21aee3aef4de3baf5a88e9e7476bde57417e54933'
    write(FIX/'payload/runtime_patch.json',dict(id='1.0.4p3',kind='internal_MOS_OP_export_and_recovery',
          base_package_manifest_sha256=sha(old),schematic_generation='UNCHANGED',simulation_deck='UNCHANGED',
          changes=['Read observed internal MOS structure names from dcOpInfo',
                   'Stop OCEAN on export errors; require complete finite data and source mapping',
                   'Resume export from a retained successful Spectre PSF into a new attempt'],
          input_report_sha256='a810cd9eed294831ed231bddca2564bea97eb26f47a344d6b9a1e878af34da67',
          school_patch_execution='NOT_RUN',actual_device_OP_values='NOT_YET_EXPORTED'))
    manifest=json.loads(old.read_text());manifest['version']='1.0.4p3';manifest['runtime_patch']='1.0.4p3'
    for n in FILES[:-1]:manifest['files'][n]=sha(FIX/'payload'/n)
    write(FIX/'payload/package_manifest.json',manifest)
    write(FIX/'patch_manifest.json',dict(id='1.0.4p3',payload={n:sha(FIX/'payload'/n) for n in FILES}))
    for p in list((FIX/'payload').glob('*.py'))+[FIX/'install.py']:ast.parse(p.read_text(),feature_version=(3,6))
    subprocess.run(['bash','-n',str(FIX/'apply.sh')],check=True)
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(FIX/'tests'),'-v'],capture_output=True,text=True)
    (FIX/'local_validation.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    write(FIX/'local_validation.json',dict(status='PASS_LOCAL_CHECKS',patch_tests=7,original_regressions=17,
          evidence=['All 13 mapped MOS leaf names occur in the returned PSF',
                    'Actual OCEAN errors cannot be hidden by a COMPLETE file or exit 0',
                    'Missing/nonfinite/mis-mapped device rows rejected',
                    'Mocked recovery calls only OCEAN; source PSF and original failure preserved',
                    'Changed source rejected; install rollback/idempotence and passive review verified'],
          limitation='No local OCEAN/SKILL execution or actual recovered device values; numerical recovery fixtures are synthetic tests only'))
    dest=BASE/'releases/project1_basic_runtime_fix_v1.0.4p3.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(FIX.rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts:continue
            i=zipfile.ZipInfo('project1_handoff/basic_runtime_fix_v1_0_4p3/'+p.relative_to(FIX).as_posix(),(2026,9,13,0,0,0))
            i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,p.read_bytes())
    dest.with_suffix('.zip.sha256').write_text(sha(dest)+'  '+dest.name+'\n')
    with zipfile.ZipFile(dest) as z:assert z.testzip() is None
    print(json.dumps(dict(zip=str(dest),size=dest.stat().st_size,sha256=sha(dest)),indent=2))


if __name__=='__main__':main()
