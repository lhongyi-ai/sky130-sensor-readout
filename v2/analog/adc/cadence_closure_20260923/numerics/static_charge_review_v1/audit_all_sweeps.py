#!/usr/bin/env python3
from pathlib import Path
import json
from read_actual_dc import read_dc, P
from metadata_review import RUNS

HERE = Path(__file__).resolve().parent
out = {'scope': 'ACTUAL_EIGHT_SWEEP_FIELD_AUDIT', 'profiles': {}}
for profile, run in RUNS.items():
    out['profiles'][profile] = {}
    for sweep in ['dc_wide_up', 'dc_wide_down', 'dc_fine_up', 'dc_fine_down']:
        _, axis, schema, rows = read_dc(run / 'input.raw' / (sweep + '.dc'))
        out['profiles'][profile][sweep] = {
            'point_count': len(rows), 'trace_field_count': len(schema),
            'external_bias_minus_requested_max_V': max(abs(r['D'] - r['SB'] - r[axis]) for r in rows),
            'raw_q_alias_max_abs_difference_C': {
                q: max(abs(r[P + ':' + q] - r[P + ':' + qi]) for r in rows)
                for q, qi in zip(['qg', 'qd', 'qs', 'qb'], ['qgi', 'qdi', 'qsi', 'qbi'])},
            'maximum_body_minus_external_SB_V': {
                q: max(abs(r[P + ':' + q] - r['SB']) for r in rows)
                for q in ['int_b', 'dbnode', 'sbnode']},
            'raw_four_q_sum_max_abs_C': max(abs(sum(r[P + ':' + q] for q in ['qg', 'qd', 'qs', 'qb'])) for r in rows),
            'reversed_matches_negative_zero_positive': all(r[P + ':reversed'] == int(r[axis] >= 0) for r in rows),
        }
(HERE / 'all_sweeps_audit.json').write_text(json.dumps(out, indent=2) + '\n')
print('All eight actual DC sweeps audited, with raw signs unchanged.')
