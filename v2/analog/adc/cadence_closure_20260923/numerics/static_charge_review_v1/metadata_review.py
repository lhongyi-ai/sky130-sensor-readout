#!/usr/bin/env python3
"""Read selected exported instance fields by TYPE STRUCT ordering, with source lines."""
from pathlib import Path
import hashlib
import json
import math
import re

HERE = Path(__file__).resolve().parent
CLOSURE = HERE.parent.parent
BASE = CLOSURE / 'runs/task_20260924T080723598851Z/design/results'
RUNS = {
    'baseline': BASE / 'baseline_20260924T080725Z_2409163',
    'strict': BASE / 'strict_20260924T080811Z_2412024',
}
INSTANCE = 'XTEST.msky130_fd_pr__pfet_01v8'


def parse_struct(path, selected):
    lines = path.read_text().splitlines()
    fields = []
    start = lines.index('"bsim4~instparams" STRUCT(') + 1
    for line in lines[start:]:
        if line == ') PROP(':
            break
        m = re.match(r'^"([^"]+)" (?:FLOAT|INT) ', line)
        if m:
            fields.append(m[1])
    value_start = lines.index(f'"{INSTANCE}" "bsim4~instparams" (') + 1
    values = []
    value_lines = []
    for number, line in enumerate(lines[value_start:], value_start + 1):
        if line == ') PROP(':
            end = number
            break
        values.append(float(line))
        value_lines.append(number)
    assert len(fields) == len(values), (path, len(fields), len(values))
    assert len(set(fields)) == len(fields)
    model = re.fullmatch(r'"model" "([^"]+)"', lines[end])
    assert model, (path, lines[end])
    result = {}
    for field in selected:
        ix = fields.index(field)
        value = values[ix]
        raw = lines[value_lines[ix] - 1]
        if not math.isfinite(value):
            status = 'NONFINITE_EXPORT_NOT_AN_EFFECTIVE_VALUE'
            value = None
        elif value == 2147483647:
            status = 'INTEGER_SENTINEL_NOT_AN_EFFECTIVE_VALUE'
            value = None
        else:
            status = 'EXPORTED_FINITE_VALUE'
        result[field] = {'raw': raw, 'value': value, 'status': status, 'line': value_lines[ix]}
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'type_field_count': len(fields), 'value_count': len(values),
            'model_attribute': model[1], 'model_line': end + 1, 'fields': result}


def main():
    out = {'status': 'LAYERED_INSTANCE_METADATA_REVIEW', 'profiles': {},
           'limit': 'File literals, exported instance fields, and effective resolved model options are different evidence layers. Sentinels/nan are not model settings.'}
    for profile, run in RUNS.items():
        p = run / 'input.raw'
        element = parse_struct(p / 'element.info', ['w', 'l', 'm', 'nf', 'rbodymod', 'rgatemod', 'trnqsmod', 'acnqsmod', 'rbpb', 'rbpd', 'rbps', 'rbdb', 'rbsb'])
        output = parse_struct(p / 'outputParameter.info', ['tempeff', 'meff', 'weff', 'leff', 'weffcv', 'leffcv'])
        assert element['model_attribute'] == output['model_attribute']
        before = json.loads((run / 'model_metadata_before.json').read_text())
        after = json.loads((run / 'model_metadata_after.json').read_text())
        assert before == after and int((run / 'model_hash_comparison_exit.txt').read_text()) == 0
        out['profiles'][profile] = {'element': element, 'outputParameter': output,
                                   'file_literal_metadata': before,
                                   'model_files_unchanged': True,
                                   'selected_bin_attribute_verified': True,
                                   'effective_capmod_cvchargemod_body_options_verified': False}
    (HERE / 'metadata_review.json').write_text(json.dumps(out, indent=2, allow_nan=False) + '\n')
    print('Exported model bin, dimensions and effective temperature read; sentinels retained as unresolved.')


if __name__ == '__main__':
    main()
