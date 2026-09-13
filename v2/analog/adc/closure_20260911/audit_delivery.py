#!/usr/bin/env python3
"""Record final software checks and immutable artifact hashes; no circuit run."""
import json
from pathlib import Path
import subprocess
import sys

import trace_replay as tr


def main():
    output = tr.HERE / 'results/delivery_audit.json'
    if output.exists():
        raise ValueError('immutable delivery audit exists')
    tests = subprocess.run([sys.executable, '-m', 'unittest', '-v', 'test_closure', 'test_resume_gate'],
                           cwd=tr.HERE, capture_output=True, text=True, timeout=60)
    blocked = subprocess.run([sys.executable, str(tr.HERE / 'resume_campaign.py'), 'run',
                              str(tr.HERE / 'campaigns/fixed_ramp32')],
                             capture_output=True, text=True, timeout=30)
    coverage_path = sorted((tr.HERE / 'campaigns/fixed_ramp32').glob('coverage_*.json'))[-1]
    coverage = json.loads(coverage_path.read_text())
    statuses = {'software_tests_18_pass': tests.returncode == 0 and 'Ran 18 tests' in tests.stderr,
                'numerical_gate_stops_execution': blocked.returncode != 0 and 'NUMERICAL_GATE_BLOCKED' in blocked.stderr,
                'strict_131073_point_grid_incomplete': coverage['status'] == 'INCOMPLETE_COVERAGE' and coverage['completed_points'] == 0 and coverage['required_points'] == 131073,
                'no_batch_directory_created': not (tr.HERE / 'campaigns/fixed_ramp32/batches').exists()}
    record = {'status': 'DELIVERY_SAFETY_CHECKS_PASS' if all(statuses.values()) else 'AUDIT_FAILED',
              'checks': statuses, 'complete_adc_qualified': False,
              'test_output': tests.stdout + tests.stderr,
              'blocked_execution_output': blocked.stdout + blocked.stderr,
              'coverage_file': str(coverage_path),
              'artifact_sha256': {str(p.relative_to(tr.HERE)): tr.sc.sha(p)
                                  for p in sorted(tr.HERE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
    tr.sc.write_json(output, record)
    print(json.dumps({'status': record['status'], 'checks': statuses, 'artifact_count': len(record['artifact_sha256']),
                      'output': str(output)}, indent=2))
    return 0 if all(statuses.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
