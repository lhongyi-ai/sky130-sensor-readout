"""Standalone local shell flow checks; fake launchers never invoke Cadence."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

FIX=Path(__file__).resolve().parents[1]
cases=[('',0,['install','recheck-passives','resume-export','run','collect']),
       ('recheck-passives',9,['install','recheck-passives','collect']),
       ('resume-export',9,['install','recheck-passives','resume-export','collect']),
       ('collect',1,['install','recheck-passives','resume-export','run','collect']),
       ('install',9,['install'])]
for failure,code,sequence in cases:
    with tempfile.TemporaryDirectory(prefix='p1_shell_flow_') as tmp:
        root=Path(tmp);log=root/'calls'
        shutil.copy2(FIX/'continue_nominal.sh',root/'continue_nominal.sh')
        (root/'apply.sh').write_text('#!/bin/bash\necho install >> "$P1_TEST_FLOW_LOG"\nif [[ "$P1_TEST_FAIL_STAGE" == install ]]; then exit 9; fi\n')
        launcher=root/'school.sh'
        launcher.write_text('#!/bin/bash\necho "$1" >> "$P1_TEST_FLOW_LOG"\nif [[ "$P1_TEST_FAIL_STAGE" == "$1" ]]; then exit 9; fi\n')
        env=dict(os.environ,P1_OP_LAUNCHER=str(launcher),P1_TEST_FLOW_LOG=str(log),P1_TEST_FAIL_STAGE=failure)
        result=subprocess.run(['bash',str(root/'continue_nominal.sh')],env=env,capture_output=True,text=True)
        assert result.returncode==code,(failure,result.returncode,result.stderr)
        assert log.read_text().splitlines()==sequence,(failure,log.read_text())
print(json.dumps({'status':'PASS_LOCAL_FAKE_LAUNCHER_FLOW','cases':len(cases)}))
