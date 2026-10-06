#!/usr/bin/env python3
"""Signed external AC response; no raw-Q interpretation or ADC pass criteria."""
from pathlib import Path
import argparse, hashlib, json, math, re

DEVICE = 'XTEST.msky130_fd_pr__pfet_01v8:'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_ac(path):
    lines = path.read_text().splitlines()
    section = None; in_prop = False; schema = {}; axis = None; rows = []; row = None
    for line in lines:
        line = line.strip()
        if line in ('SWEEP', 'TRACE', 'VALUE'):
            section = line; continue
        if in_prop:
            if line == ')': in_prop = False
            continue
        if section in ('SWEEP', 'TRACE'):
            match = re.fullmatch(r'"([^"]+)" "([^"]+)"(?: PROP\()?', line)
            if match:
                if section == 'SWEEP':
                    if axis is not None: raise ValueError('Multiple sweep axes unsupported')
                    axis = match[1]
                else:
                    if match[1] in schema: raise ValueError('Duplicate TRACE signal')
                    schema[match[1]] = match[2]
                in_prop = line.endswith('PROP(')
            elif line and line != 'END':
                raise ValueError('Unsupported actual schema: '+line)
        elif section == 'VALUE':
            if line in ('', 'END'): continue
            match = re.fullmatch(r'"([^"]+)"\s+(.+)', line)
            if not match: raise ValueError('Unsupported value line: '+line)
            name, raw = match.groups()
            if name == axis:
                if row is not None: rows.append(row)
                row = {axis: float(raw)}
                continue
            if row is None: raise ValueError('Signal before sweep coordinate')
            if name in row: raise ValueError('Duplicate signal at sweep point: '+name)
            if name not in schema: raise ValueError('Undeclared signal: '+name)
            z = re.fullmatch(r'\(([^\s]+)\s+([^\s]+)\)', raw)
            if not z: raise ValueError('Expected actual complex encoding: '+raw)
            row[name] = complex(float(z[1]), float(z[2]))
    if row is not None: rows.append(row)
    if axis != 'freq' or len(rows)<2 or not schema: raise ValueError('Missing frequency sweep')
    for row in rows:
        if set(row) != {axis, *schema}: raise ValueError('Incomplete actual AC row')
        if not all(math.isfinite(complex(v).real) and math.isfinite(complex(v).imag) for v in row.values()):
            raise ValueError('Nonfinite actual AC value')
    if not all(a[axis] < b[axis] for a,b in zip(rows,rows[1:])): raise ValueError('Nonascending or duplicate frequency')
    return schema, rows

def port_column(row):
    # Each source's positive terminal is at the measured device node.
    # KCL: I_device + I_vsource_positive_terminal = 0.
    required = {'freq', 'D', 'G', 'SB', 'VD:p', 'VG:p', 'VS:p'}
    if not required <= set(row): raise ValueError('Missing measured external port: '+str(required-set(row)))
    if row['G'] != 0 or row['SB'] != 0:
        raise ValueError('G/SB excitation is not exactly zero; not a D-only Y column')
    drive = row['D']
    if drive == 0: raise ValueError('Zero actual D excitation')
    omega = 2*math.pi*row['freq']
    current = {'D': -row['VD:p'], 'G': -row['VG:p'], 'SB': -row['VS:p']}
    out = {'frequency_Hz': row['freq'], 'actual_D_excitation_V': [drive.real,drive.imag], 'ports': {}}
    for port, value in current.items():
        y = value/drive
        out['ports'][port] = {'I_device_A': [value.real,value.imag], 'Y_kD_S': [y.real,y.imag], 'G_kD_S': y.real, 'C_effective_kD_F': y.imag/omega}
    residual = sum(current.values())
    scale = sum(abs(i) for i in current.values())
    out['KCL_sum_external_device_currents_A'] = [residual.real,residual.imag]
    out['KCL_residual_fraction_of_sum_magnitudes'] = abs(residual)/scale if scale else 0.0
    # Direct device terminals, when present, are an independent sign/KCL crosscheck.
    if all(DEVICE+k in row for k in 'dgsb'):
        direct = {'D': row[DEVICE+'d'], 'G': row[DEVICE+'g'], 'SB': row[DEVICE+'s']+row[DEVICE+'b']}
        out['source_vs_direct_device_current_residual_A'] = {p: [float((current[p]-direct[p]).real),float((current[p]-direct[p]).imag)] for p in current}
    return out

def analyze(run):
    manifest = json.loads((run/'package_manifest.json').read_text())
    case = (run/'case.txt').read_text().strip(); expected = manifest['cases'][case]
    if sha(run/'input.scs') != expected['sha256']: raise ValueError('Input differs from frozen case')
    if int((run/'exit_code.txt').read_text()) != 0: raise ValueError('Spectre did not exit successfully')
    if int((run/'model_hash_comparison_exit.txt').read_text()) != 0: raise ValueError('Model metadata changed during execution')
    before = json.loads((run/'model_metadata_before.json').read_text())
    after = json.loads((run/'model_metadata_after.json').read_text())
    if before != after: raise ValueError('Model metadata differs before/after')
    candidates = [p for p in (run/'input.raw').glob('acBoundary.*') if p.suffix=='.ac']
    if len(candidates)!=1: raise ValueError('Need one actual acBoundary AC raw file')
    path = candidates[0]; schema, rows = read_ac(path)
    grid = manifest['frequency_Hz']
    if len(rows) != grid['expected_points']: raise ValueError('Unexpected frequency point count')
    for i,row in enumerate(rows):
        expected_f = grid['start']*10**(i/grid['points_per_decade'])
        # File/grid round-trip check only, not a circuit acceptance tolerance.
        if not math.isclose(row['freq'], expected_f, rel_tol=1e-12): raise ValueError('Unexpected frequency grid')
    log = (run/'spectre.out').read_text(errors='replace')
    endings = re.findall(r'spectre completes with [^\n]+', log)
    if not endings: raise ValueError('No Spectre completion summary')
    return {
        'status': 'ACTUAL_AC_EXTERNAL_PORT_RESPONSE_ONLY', 'case': case, 'requested_delta_D_minus_SB_V': expected['delta_D_minus_SB_V'],
        'run': str(run), 'input_sha256': sha(run/'input.scs'), 'raw_sha256': sha(path),
        'actual_trace_schema': schema, 'actual_frequency_points': len(rows), 'log_completion': endings,
        'model_metadata_before_after_equal': True,
        'OP_bias_and_reversed_review': 'REQUIRES_SEPARATE_ACTUAL_OP_FILE_REVIEW',
        'rows': [port_column(row) for row in rows],
        'limitations': manifest['not_claimed'], 'complete_ADC': False, 'full_ADC_accuracy_pass': False, 'formal_ADC_PEX_allowed': False,
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args(); result = analyze(args.run)
    if args.output.exists(): raise FileExistsError('Preserve existing analysis; choose a new output')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'])
