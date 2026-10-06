"""Regression for the actual singular-warning pilot log; no simulation involved."""
from pathlib import Path
import json,hashlib
from completion_summary import parse_completion,execution_completed
ROOT=Path(__file__).resolve().parent
f=ROOT/'runs/tg_f60_base_white_s11/20260923T113429Z_e297ba3c/spectre.out'
log=f.read_text();line=[x for x in log.splitlines() if x.lower().startswith('spectre completes')][-1]
assert parse_completion(log)=={'errors':0,'warnings':1}
assert execution_completed(0,log)
assert not execution_completed(1,log)
assert parse_completion('spectre completes with 0 errors, 0 warnings, and 3 notices.')=={'errors':0,'warnings':0}
assert not execution_completed(0,'spectre completes with 1 error, 0 warnings, and 1 notice.')
assert not execution_completed(0,'spectre completes with 2 errors, 1 warning, and 1 notice.')
assert not execution_completed(0,'Simulation still running')
assert not execution_completed(0,'spectre completes with 0 errors, 0 warnings.\nspectre completes with 1 error, 1 warning.')
report={'status':'LOCAL_LOG_PARSER_REGRESSION_PASS','source_log_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'actual_summary_line':line,'cases':8,'simulation_repeated':False,'numeric_qualification':'NOT_PASSED_LTE_WARNING_REQUIRES_CONVERGENCE_REVIEW'}
(ROOT/'completion_regression_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
