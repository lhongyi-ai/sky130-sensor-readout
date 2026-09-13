"""Reproduce local returned-data review in an isolated package snapshot."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]
FIX=BASE/'runtime_fixes/v1_0_4p2'
sys.path[:0]=[str(FIX/'payload'),str(BASE/'basic_design')]
import run
from passive_review import review_passives,sha


def main():
    with tempfile.TemporaryDirectory(prefix='p1_review_snapshot_') as tmp:
        with zipfile.ZipFile(BASE/'releases/project1_basic_design_v1.0.4.zip') as z: z.extractall(tmp)
        root=Path(tmp)/'project1_handoff/basic_design_v1_0_4'
        for folder in [BASE/'runtime_fixes/v1_0_4p1/payload', FIX/'payload']:
            for p in folder.iterdir():
                if p.is_file(): shutil.copy2(p,root/p.name)
        shutil.copytree(ROOT/'received/runs',root/'runs',dirs_exist_ok=True)
        cfg=json.loads((ROOT/'received/site.json').read_text())
        review=review_passives(root,cfg,run.deck,run.netlist_body,run.log_audit,check_model=False)
        review['source_report_sha256']=sha(ROOT/'project1_basic_report_20260913T010855Z_58477ef8.zip')
        review['local_review_status']='PASS_RETURNED_DATA_REVIEW' if review['status']=='PASS' else 'FAIL'
        review['school_patch_execution']='NOT_RUN'
        review['limitations'].append('Local review does not access the installed school model; Linux recheck requires its entry hash to match.')
        (ROOT/'passive_review_v1.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:review[k] for k in ['status','local_review_status','current_site_model_checked','source_report_sha256']},indent=2))


if __name__=='__main__':main()
