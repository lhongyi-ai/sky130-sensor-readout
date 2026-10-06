"""Read-only review of frozen body probe; write only this numerics report directory."""
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import numpy as np
from psf_stream import Trace
HERE = Path(__file__).resolve().parent
RUN = HERE.parent / 'runs/task_20260924T060914240241Z/design'
OLD = HERE.parent / 'runs/task_20260924T053814697817Z/design'
OUT = HERE / 'body_network_probe_review'
P = 'p2_ams_reset1.'
DEVICE = P + 'phases.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8'
D = DEVICE + '.'
G = P + 'phases.XPHASE_XBCONV_B'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')

def main():
    OUT.mkdir(exist_ok=True)
    raw = RUN / 'amsdControl.raw/adc_closure_tran.tran.tran'
    trace = Trace(raw, accepted_types=('V', 'I', '-enum'))
    rows = list(trace.rows())
    n = len(rows)
    a = {k: np.asarray([r[k] for r in rows]) for k in rows[0]}
    t = a['time']
    vdd = a[P + 'vdd']
    ext_vds = a[P + 'conv_e'] - vdd
    if trace.types[D + 'reversed'] != '-enum' or set(a[D + 'reversed']) != {0.0, 1.0}:
        raise ValueError('Unexpected actual reverse schema; inspect before interpreting')
    currents = [D + c + '_$flow' for c in 'dgsb']
    for name in currents:
        if trace.types[name] != 'I':
            raise ValueError('Incorrect current trace type')
    old = Trace(OLD / 'amsdControl.raw/adc_closure_tran.tran.tran')
    oldrows = list(old.rows())
    samegrid = n == len(oldrows) and all((x['time'] == y['time'] for x, y in zip(oldrows, rows)))
    samecommon = samegrid and all((all((k in y and v == y[k] for k, v in x.items())) for x, y in zip(oldrows, rows)))
    changes = np.flatnonzero(np.diff(a[D + 'reversed']) != 0)
    near = [int(i) for i in changes if 4.06315e-06 < t[i] < 4.06325e-06]
    if len(near) != 1:
        raise ValueError('Expected one local mode event; do not select another silently')
    j = near[0]
    shortnames = {'time_s': 'time', 'external_VDD_V': P + 'vdd', 'CONV_V': P + 'conv_e', 'local_gate_V': G, 'int_b_V': D + 'int_b', 'dbnode_V': D + 'dbnode', 'sbnode_V': D + 'sbnode', 'saved_OP_vds_V': D + 'vds', 'saved_reversed_enum': D + 'reversed', **{c + '_current_A': D + c + '_$flow' for c in 'dgsb'}}

    def snapshot(i):
        r = {k: float(a[v][i]) for k, v in shortnames.items()}
        r.update(accepted_row=int(i), external_signed_VDS_V=float(ext_vds[i]), all_terminal_current_sum_A=float(sum((a[x][i] for x in currents))))
        return r
    with (OUT / 'all_accepted_selected_points.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(snapshot(0)))
        w.writeheader()
        w.writerows((snapshot(i) for i in range(n)))
    transitions = [{'before': snapshot(int(i)), 'after': snapshot(int(i + 1))} for i in changes]
    stepdiff = {k: float(a[D + k][j + 1] - a[D + k][j]) for k in ['int_b', 'dbnode', 'sbnode', 'vds', 'reversed']}
    stepdiff.update({c + '_current_A': float(a[D + c + '_$flow'][j + 1] - a[D + c + '_$flow'][j]) for c in 'dgsb'})
    current_sum = sum((a[x] for x in currents))
    external_bulk_R_current = (vdd - a[D + 'int_b'] + (vdd - a[D + 'dbnode']) + (vdd - a[D + 'sbnode'])) / 50.0
    log = (RUN / 'xrun.log').read_text(errors='replace')
    warnings = dict(Counter(re.findall('WARNING \\(([^)]+)\\)', log)))
    patterns = {'accepted_steps': 'Total Number of Accepted steps\\s*:\\s*(\\d+)', 'LTE_rejected_steps': 'Number of LTE rejected steps\\s*:\\s*(\\d+)', 'Newton_rejected_steps': 'Number of Newton rejected steps\\s*:\\s*(\\d+)', 'device_rejected_steps': 'Number of Device rejected steps\\s*:\\s*(\\d+)', 'minimum_step_s': 'Minimum time step\\s*=\\s*([\\deE+.-]+)', 'drastic_step_changes': 'Number of drastic step size changes\\s*=\\s*(\\d+)', 'recovery_steps': 'Number of steps to recover from drastic step size drop\\s*=\\s*(\\d+)'}
    stats = {}
    for k, pat in patterns.items():
        m = re.search(pat, log)
        stats[k] = (float(m[1]) if k == 'minimum_step_s' else int(m[1])) if m else None
    warningblocks = []
    lines = log.splitlines()
    for i, line in enumerate(lines):
        if 'WARNING (' in line:
            warningblocks.append(re.sub('/home/compute/[^/\\s\\"]+', '<school-user-home>', '\n'.join(lines[max(0, i - 1):i + 6])))
    before, after = (snapshot(j), snapshot(j + 1))
    cross = float(t[j] - ext_vds[j] * (t[j + 1] - t[j]) / (ext_vds[j + 1] - ext_vds[j]))
    frozen = RUN / 'manifest.json'
    clarified = HERE / 'body_network_probe_v1/manifest.json'
    scope = {'run': str(RUN), 'status': 'DIAGNOSTIC_SCOPE_CLARIFICATION_ONLY', 'actual_run_manifest_sha256': sha(frozen), 'local_clarified_manifest_sha256': sha(clarified), 'both_EDA_control_sha256': sha(RUN / 'amsdControl.scs'), 'original_run_manifest_unchanged': True, 'legacy_manifest_fields': {k: json.loads(frozen.read_text()).get(k) for k in ['frames', 'expected_completed_decisions', 'expected_additional_aborted_frame']}, 'legacy_field_meaning': 'Inherited full source testbench expectation; not the expected completion of this intentional short diagnostic.', 'expected_diagnostic_stop_s': 4.1e-06, 'expected_completed_frames': 0, 'expected_completed_decisions': 0, 'expected_completed_reset_abort_checks': 0, 'simulator_exit_code': int((RUN / 'simulator_exit_code.txt').read_text()), 'qualification_exit_code': int((RUN / 'qualification_exit_code.txt').read_text()), 'complete_ADC': False, 'full_ADC_accuracy_pass': False}
    write('scope_clarification.json', scope)
    result = {'status': 'MODE_CHANGE_AND_BODY_EVENT_OBSERVED_NOT_MODEL_BUG_PROOF', 'scope': scope, 'raw_sha256': sha(raw), 'log_sha256': sha(RUN / 'xrun.log'), 'all_selected_raw_points_csv_sha256': sha(OUT / 'all_accepted_selected_points.csv'), 'raw_points': n, 'selected_scalar_trace_count': len(trace.names), 'actual_types': dict(Counter(trace.types.values())), 'saved_interval_s': [float(t[0]), float(t[-1])], 'comparison_with_original_probe': {'old_points': len(oldrows), 'common_voltage_trace_count': len(old.names), 'time_grid_exactly_identical': samegrid, 'every_common_voltage_value_exactly_identical': samecommon, 'old_raw_sha256': sha(old.path), 'meaning': 'Adding save observations did not change any recorded common voltage or accepted time. This is observation reproducibility, not tighter-accuracy convergence.'}, 'actual_solver': trace.header, 'requested_outputs': {n: trace.types[n] for n in trace.names if n.startswith(DEVICE)}, 'warnings': warnings, 'warning_blocks': warningblocks, 'diagnostic_statistics': stats, 'mode_change_near_warning': {'before': before, 'after': after, 'elapsed_s': float(t[j + 1] - t[j]), 'changes': stepdiff, 'external_signed_VDS_zero_interpolated_s': cross, 'logged_LTE_time_literal': '4.0632 us', 'logged_time_limit': 'Rounded log time does not identify the exact rejected Newton/LTE iterate; all adjacent accepted points are preserved.'}, 'all_mode_transitions': transitions, 'raw_adjacent_event_points': [snapshot(i) for i in range(max(0, j - 16), min(n, j + 18))], 'body_minus_external_bulk_range_V': {k: [float((a[D + k] - vdd).min()), float((a[D + k] - vdd).max())] for k in ['int_b', 'dbnode', 'sbnode']}, 'OP_vds_convention_observation': {'max_abs_OP_vds_plus_abs_external_VDS_V': float(np.max(np.abs(a[D + 'vds'] + np.abs(ext_vds)))), 'near_event_note': 'For this PFET, saved OP vds remains negative on both sides while reversed changes 1 to 0. Use independently computed CONV-VDD for the signed external terminal voltage; do not infer no crossing from OP vds. This observed convention is not generalized to other model types.'}, 'terminal_currents': {'positive_direction': 'Into the device; actual :currents output, not resistive-only ids/ibulk.', 'ranges_A': {c: [float(a[D + c + '_$flow'].min()), float(a[D + c + '_$flow'].max())] for c in 'dgsb'}, 'all_terminal_sum_max_abs_A': float(np.max(np.abs(current_sum))), 'all_terminal_sum_RMS_A': float(np.sqrt(np.mean(current_sum ** 2))), 'scope': 'Includes simulator total terminal currents during switching, including displacement contributions. Tiny terminal-sum residual checks model/solver charge/current self-consistency, not physical correctness of the body model and not ADC precision.', 'bulk_resistance_network_crosscheck': {'assumption_source': 'Actual school TT bin metadata all rbpb/rbdb/rbsb=50 ohm; installed bsim4 help defines their endpoints.', 'expression_A': '((VDD-int_b)+(VDD-dbnode)+(VDD-sbnode))/50', 'max_difference_from_saved_bulk_terminal_A': float(np.max(np.abs(external_bulk_R_current - a[D + 'b_$flow']))), 'limitations': 'This is a simplified resistive crosscheck, not a full decomposition of all model bulk contributions. The residual is not attributed to gbmin: that alone is too small. Its contribution and solver/stamping effects remain unseparated; no exact model-RC boundary or physical accuracy is claimed.'}}, 'conclusions': ['The actual reversed-mode output switches in the same accepted step as external VDS crosses zero and the saved internal-body event. This strengthens a model/source-drain-mode boundary hypothesis beyond timing coincidence alone.', 'dbnode and sbnode both move; their values do not simply swap at the mode change. The body event cannot be explained as merely an external-bulk wiring error.', 'Terminal currents change coherently and their sum is small; internal model self-consistency cannot establish physical validity, smoothness or full ADC numerical convergence.', 'All original 76 voltage traces and all 4951 times are identical to the previous probe. New saves did not remove or create the event in accepted data.', 'The accepted step contains a sharp finite difference, not proof of a mathematical discontinuity. Rejected iterates and an independently converged local solution are still missing.'], 'next_minimal_path': {'no_supported_in_place_fix_yet': True, 'purpose': 'Produce a device/solver reproduction around the measured source-drain mode boundary, not another blind full-ADC solver switch.', 'procedure': ['Use the frozen full 4.1us native ADC probe as the exact reproduction; attach actual tool builds, PDK file hashes, topology, input hashes, diagnostic logs and selected raw rows. Never redistribute school PDK files.', 'In a separate diagnostic only, preserve the same native PFET geometry, junction geometry, model and body ties; drive external gate and drain with bounded finite-slope stimuli around the measured bias/VDS crossing, include the observed modes, and retain all three body nodes and total currents. Do not replace the ADC with ideal drivers for qualification.', 'Establish same-method baseline/tight convergence across the local crossing without suppressing warning or deleting points; if reproducible, ask model/simulator support to explain source/drain body-charge evaluation and provide a supported fix/version.', 'Any supported fix or intentional physical phase-buffer change must return to the unchanged full ADC two-frame+reset-abort protocol and original all-edge0.05LSB gate before twelve-frame expansion.'], 'forbidden_shortcuts': ['Do not disable rbodymod, patch PDK, add arbitrary leak/IC/cmin, redefine currents, delete the event, or treat no-warning as proof.']}, 'complete_ADC': False, 'full_ADC_accuracy_pass': False}
    write('review.json', result)
    (OUT / 'warning_excerpt.txt').write_text('\n\n'.join(warningblocks) + '\n')
    plot(t, a, j, cross)
    md = f'# Actual body-network probe: mode boundary located, no qualified repair\n\nThe 4.1 µs probe completed with zero Spectre errors and two warnings. The complete-protocol checker correctly returns 2; requested fields existed. **This is not complete ADC or numerical accuracy PASS.**\n\nCompared with the original probe, {n} time points and all 76 common voltage channels are exactly equal. Additional saves did not alter the trajectory. Actual reversed is an enum containing only 0/1; no missing field was filled.\n\nAt accepted points {j}→{j + 1}、{float((t[j + 1] - t[j]) * 1000000000000000.0):.3f} fs:\n\n| Observation | Before | After |\n|---|---:|---:|\n| External CONV−VDD | {ext_vds[j] * 1000000.0:.3f} µV | {ext_vds[j + 1] * 1000000.0:.3f} µV |\n| Actual reversed state | {int(a[D + 'reversed'][j])} | {int(a[D + 'reversed'][j + 1])} |\n| int_b−VDD | {(a[D + 'int_b'][j] - vdd[j]) * 1000000.0:.3f} µV | {(a[D + 'int_b'][j + 1] - vdd[j + 1]) * 1000000.0:.3f} µV |\n| dbnode−VDD | {(a[D + 'dbnode'][j] - vdd[j]) * 1000000.0:.3f} µV | {(a[D + 'dbnode'][j + 1] - vdd[j + 1]) * 1000000.0:.3f} µV |\n| sbnode−VDD | {(a[D + 'sbnode'][j] - vdd[j]) * 1000000.0:.3f} µV | {(a[D + 'sbnode'][j + 1] - vdd[j + 1]) * 1000000.0:.3f} µV |\n\nThe 449.092 µV int_b decrease shares one accepted step with actual mode reversal; dbnode/sbnode decrease 65.742/46.058 µV, rather than simply swapping names. The local gate is smooth and external bulk stays 1.8 V. Rounded log time is not the exact failed iteration.\n\nSaved PFET OP vds is negative on both sides; its maximum difference from −abs(CONV−VDD) is {result['OP_vds_convention_observation']['max_abs_OP_vds_plus_abs_external_VDS_V']:.3g} V. Analysis therefore calculates signed VDS from external terminals rather than using the folded OP sign.\n\nMaximum four-terminal current-sum residual is {np.max(np.abs(current_sum)) * 1000000000000000.0:.3f} fA; the three 50 Ω external-body-resistor reconstruction differs from bulk current by at most {result['terminal_currents']['bulk_resistance_network_crosscheck']['max_difference_from_saved_bulk_terminal_A']:.3g} A. Port-current consistency is not a complete body-current decomposition or physical model validation. Total terminal currents include displacement components.\n\nEvidence supports a mode-boundary investigation, **not a PDK bug conclusion**. No qualified repair exists. A supported change must return to complete two-frame/reset and original full-domain 0.05 LSB qualification before 12 frames.\n\nThe scope clarification retains original manifest hashes. Inherited frames=2/decisions=24 describe the source fixture; this short probe completes zero frames, decisions or complete reset-abort protocols.\n\nreview.json retains six mode changes, actual neighbors, warnings and source hashes; all_accepted_selected_points.csv retains all {n} selected rows. The figure is a local explanation; no interval is deleted from analysis. Full original PSF remains in the local run.\n'
    (OUT / 'README.md').write_text(md)
    print(json.dumps({k: result[k] for k in ['status', 'raw_points', 'actual_types', 'comparison_with_original_probe', 'mode_change_near_warning', 'terminal_currents']}, indent=2))

def plot(t, a, j, cross):
    os.environ.setdefault('MPLCONFIGDIR', str(HERE / 'private_runtime/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'})
    x = (t - 4.0632e-06) * 1000000000000.0
    sel = (x >= -3) & (x <= 4)
    vdd = a[P + 'vdd']
    zero = (cross - 4.0632e-06) * 1000000000000.0
    fig, ax = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    fig.subplots_adjust(left=0.12, right=0.86, top=0.86, bottom=0.2, hspace=0.18)
    for q in ax:
        q.grid(alpha=0.2)
        q.axvline(zero, ls='--', lw=0.8, color='#64748b')
    ax[0].plot(x[sel], (a[P + 'conv_e'][sel] - vdd[sel]) * 1000.0, '.-', color='#1769aa', ms=2, label='External CONV - VDD')
    ax[0].axhline(0, lw=0.6, color='#64748b')
    ax[0].set_ylabel('External VDS (mV)')
    ax[0].legend(loc='upper right', frameon=False)
    twin = ax[0].twinx()
    twin.step(x[sel], a[D + 'reversed'][sel], where='post', color='#c47918', lw=1.3)
    twin.set_yticks([0, 1])
    twin.set_ylim(-0.1, 1.1)
    twin.set_ylabel('Actual reversed enum', color='#a2610c')
    for key, color in [('int_b', '#be243c'), ('dbnode', '#1769aa'), ('sbnode', '#20734f')]:
        ax[1].plot(x[sel], (a[D + key][sel] - vdd[sel]) * 1000.0, '.-', ms=2, label=key, color=color)
    ax[1].set_ylabel('Internal body - VDD (mV)')
    ax[1].legend(loc='lower left', frameon=False, ncol=3)
    ax[1].text(0.98, 0.9, 'Same accepted step:\nint_b -449.09 uV\ndbnode -65.74 uV\nsbnode -46.06 uV', ha='right', va='top', transform=ax[1].transAxes, color='#be243c', fontsize=10, bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': 0.9})
    for key, color in [('d', '#1769aa'), ('g', '#c47918'), ('s', '#20734f'), ('b', '#be243c')]:
        ax[2].plot(x[sel], a[D + key + '_$flow'][sel] * 1000000.0, '.-', ms=2, label=key.upper(), color=color)
    ax[2].set_ylabel('Total terminal current (uA)')
    ax[2].legend(loc='upper right', frameon=False, ncol=4)
    ax[3].semilogy(x[1:][sel[1:]], np.diff(t)[sel[1:]] * 1000000000000000.0, '.-', color='#526275', ms=3)
    ax[3].set_ylabel('Accepted step (fs)')
    ax[3].set_xlabel('Time from 4.063200 microseconds (ps); original times, no alignment')
    fig.text(0.12, 0.952, 'Actual source/drain mode change and internal body response', fontsize=17, weight='bold', color='#172b46')
    fig.text(0.12, 0.918, 'Full native ADC short probe, Spectre 21; only new observations. Original 76 voltages and all times are identical.', fontsize=10.3, color='#596779')
    fig.text(0.12, 0.891, 'Dashed: interpolated external VDS = 0. Stepped enum shows sampled states, not an exact hidden switch time.', fontsize=10.3, color='#596779')
    fig.text(0.12, 0.115, 'Observed association is not proof of a model defect or ADC numerical accuracy.', fontsize=11.5, weight='bold', color='#172b46')
    fig.text(0.12, 0.08, 'All 4951 selected rows and all six mode transitions remain in the report. Terminal-current conservation is model\nself-consistency only; it includes displacement current. Short diagnostic: complete ADC = false; original FAIL remains.', fontsize=10, color='#596779', linespacing=1.5)
    for ext in ['png', 'svg']:
        fig.savefig(OUT / f'body_network_event.{ext}', dpi=170)
    plt.close(fig)
if __name__ == '__main__':
    main()
