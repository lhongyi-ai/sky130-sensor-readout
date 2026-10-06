#!/bin/bash
set -euo pipefail
cd '__RUN__'
set +e
bash run_case.sh baseline 180
P1_BASE=$?
if [ "$P1_BASE" -eq 0 ]; then bash run_case.sh strict 180; P1_STRICT=$?; else P1_STRICT=125; fi
set -e
python3 - "$P1_BASE" "$P1_STRICT" <<'PY'
import json,sys
from pathlib import Path
summary={'scope':'FULL_NATIVE_FIRST_EDGE_DIAGNOSIS_ONLY','baseline_exit':int(sys.argv[1]),'strict_exit':int(sys.argv[2]),'full_ADC_numeric_qualified':False}
Path('summary.json').write_text(json.dumps(summary,indent=2)+'\n')
PY
tar -czf results.tar.gz results
printf '0\n' >exit_code.txt
