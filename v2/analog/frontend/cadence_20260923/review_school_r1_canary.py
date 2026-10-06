"""Read separately named real PSF analyses; no simulation or remote commands."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BRIDGE = Path('/path/to/virtuoso-bridge-lite')
sys.path.insert(0, str(BRIDGE / 'src'))
from virtuoso_bridge.spectre.parsers import parse_spectre_psf_ascii
RUN = ROOT / 'v2/cadence/linuxlab_20260923/runs/spectre_canary_20260923T100631141401Z'
NATIVE = ROOT / 'v2/cadence/linuxlab_20260923/runs/p2fe_c06_school_r1_20260923T100510581533Z'
OLD = HERE.parent / 'dynamic_20260911/diagnostics/07_20260911T085157880653Z_candidate_06'
CANARY = HERE.parent / 'qualification_20260913/runs/20260913T062412790986Z_noise_g4_acquire'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def complex_json(value):
    return {'real': float(value.real), 'imag': float(value.imag)}

def main():
    data = {}
    paths = [RUN / 'native_netlist', RUN / 'input.scs', RUN / 'spectre.out', NATIVE / 'audit.json', HERE / 'native_canary_school_r1_objects.json', OLD / 'columns.json', OLD / 'dc.dat', OLD / 'bench.spice', CANARY / 'op.dat', CANARY / 'ac.dat', CANARY / 'dc.dat', BRIDGE / 'src/virtuoso_bridge/spectre/parsers.py']
    for name in ('dcOp.dc', 'ac.ac', 'dc.dc', 'dcOpInfo.info'):
        p = RUN / 'input.raw' / name
        paths.append(p)
        result = parse_spectre_psf_ascii(p)
        assert result.status.value == 'success', name
        data[name] = result.data
    op, ac, dc, info = [data[x] for x in ('dcOp.dc', 'ac.ac', 'dc.dc', 'dcOpInfo.info')]
    assert dc['SW'] == [-0.32, 0.0, 0.32]
    assert len(ac['freq']) == 161
    selected_nodes = ['VINP', 'VINN', 'IP', 'IN', 'OP', 'ON', 'FP', 'FN', 'HP', 'HN', 'XPGA_SUMPOS', 'XPGA_SUMNEG', 'XPGA_XFP4_N', 'XPGA_XFN4_N', 'XPGA_XOTA_BN', 'XPGA_XOTA_BP', 'XPGA_XOTA_TAIL', 'XPGA_XOTA_N1', 'XPGA_XOTA_N2', 'XPGA_XOTA_NCM', 'XPGA_XOTA_CMS', 'XPGA_XOTA_CMG', 'XPGA_XOTA_CS', 'XPGA_XOTA_CR', 'XPGA_XOTA_CTAIL', 'XPGA_XOTA_DS', 'XPGA_E1', 'XPGA_E1B', 'XPGA_E4', 'XPGA_E4B', 'XPGA_E16', 'XPGA_E16B', 'XPGA_XN16_N']
    nodes = {k: op[k] for k in selected_nodes}
    mos = {}
    for name in ['XMIP', 'XMIN', 'XMTAIL', 'XMLP', 'XMLN', 'XMSP', 'XMSN', 'XMOP', 'XMON', 'XCMS', 'XCMR', 'XCMT', 'XBIAS_XDBN']:
        prefix = 'XPGA_XOTA_' + name + '.'
        vals = {k.split(':')[-1]: v for k, v in info.items() if k.startswith(prefix) and k.split(':')[-1] in ('ids', 'gm', 'gds', 'vgs', 'vds', 'vth', 'vdsat', 'region')}
        assert len(vals) == 8
        vals['abs_vds_minus_abs_vdsat_v'] = abs(vals['vds']) - abs(vals['vdsat'])
        mos[name] = vals
    resistor_op = {}
    for obj in json.loads((HERE / 'native_canary_school_r1_objects.json').read_text()):
        if obj['kind'] != 'resistor':
            continue
        prefix = obj['name'] + '.'
        members = {k: v for k, v in info.items() if k.startswith(prefix) and k.split(':')[-1] in ('res', 'v', 'i')}
        resistor_op[obj['name']] = {'components': members, 'sum_internal_model_res_ohm': sum((v for k, v in members.items() if k.endswith(':res')))}
    ac_audit = []
    for hz in (1.0, 1000.0):
        i = int(np.argmin(abs(np.array(ac['freq']) - hz)))
        assert abs(ac['freq'][i] / hz - 1) < 1e-10
        a = {k: v[i] for k, v in ac.items() if isinstance(v, list)}
        ri = (a['IP'] - a['XPGA_SUMPOS']) / a['RSP:1']
        feedback_i = a['XPGA_XFP4_XR_XR.rend:bs_p1']
        rf = (a['ON'] - a['XPGA_XFP4_N']) / feedback_i
        ron = (a['XPGA_XFP4_N'] - a['XPGA_SUMPOS']) / feedback_i
        core_A = (a['OP'] - a['ON']) / (a['XPGA_SUMPOS'] - a['XPGA_SUMNEG'])
        gain = (a['FP'] - a['FN']) / (a['VINP'] - a['VINN'])
        ideal_ratio = (rf + ron) / (350 + ri)
        finite_gain_prediction = ideal_ratio / (1 + (1 + ideal_ratio) / core_A)
        ac_audit.append({'frequency_hz': ac['freq'][i], 'sensor_to_filter_diff_gain': complex_json(gain), 'sensor_to_filter_diff_gain_abs': abs(gain), 'Rin_ac_ohm': complex_json(ri), 'Rfb_ac_ohm': complex_json(rf), 'feedback_switch_ac_ohm': complex_json(ron), 'core_A_at_this_closed_OP': complex_json(core_A), 'resistive_feedback_ratio': complex_json(ideal_ratio), 'finite_A_core_gain_prediction': complex_json(finite_gain_prediction), 'scope': 'At low frequency, neglects small leakage/displacement terms; output filter creates additional phase. Source AC PSF numerical precision limits algebraic agreement.'})
    old_canary_op = np.loadtxt(CANARY / 'op.dat', skiprows=1, ndmin=2)[0]
    old_canary_ac = np.loadtxt(CANARY / 'ac.dat', skiprows=1, ndmin=2)[0]
    old_canary_dc = np.loadtxt(CANARY / 'dc.dat', skiprows=1, ndmin=2)
    old_cm = float((old_canary_op[3] + old_canary_op[4]) / 2)
    new_cm = (op['FP'] + op['FN']) / 2
    old_gain = float(old_canary_ac[1] * 4)
    old_cols = json.loads((OLD / 'columns.json').read_text())['dc']
    old_dc = np.loadtxt(OLD / 'dc.dat', skiprows=1)
    zero = int(np.argmin(abs(old_dc[:, 0])))
    assert abs(old_dc[zero, 0]) < 1e-12
    old_g4_nodes = {k: float(old_dc[zero, i]) for i, k in enumerate(old_cols) if k.startswith(('v(xg4.', 'i(v.xg4.'))}
    device_cols = [(i, k) for i, k in enumerate(old_cols) if k.startswith('@m.')]
    constant_cols = [k for i, k in device_cols if len(set(old_dc[:, i])) == 1]
    assert len(constant_cols) == len(device_cols) == 210
    old_xmsp_key = '@m.xg4.xdut.xota.xmsp.msky130_fd_pr__pfet_01v8[vds]'
    old_xmsp_vds = float(old_dc[zero, old_cols.index(old_xmsp_key)])
    old_node_vsd = 1.8 - old_g4_nodes['v(xg4.corep)']
    notices = [line.strip() for line in (RUN / 'spectre.out').read_text().splitlines() if any((key in line for key in ('Notice from spectre', 'GminDC', 'dV(', 'spectre completes with')))]
    output = {'status': 'SCHOOL_R1_REAL_CANARY_EXECUTED__M2_UNQUALIFIED', 'data_source_policy': 'dcOp.dc, dc.dc, ac.ac and dcOpInfo.info parsed independently; merged result.json deliberately not used.', 'hashes': {str(p): sha(p) for p in paths}, 'native_audit_status': json.loads((NATIVE / 'audit.json').read_text())['status'], 'sample_counts': {'OP': 1, 'DC': 3, 'AC': 161}, 'op_nodes_v': nodes, 'core_mos_op': mos, 'physical_resistor_op': resistor_op, 'power_vdd_plus_vcm_w': -1.8 * op['VDD_SRC:p'] - 0.9 * op['VCM:p'], 'scope_of_power': 'Static frontend assembly VDD+VCM only; no full ADC/digital switching or whole-core qualification.', 'dc_points': [{'SW_v': s, 'sensor_diff_v': s / 4, 'output_diff_v': p - n, 'output_cm_v': (p + n) / 2} for s, p, n in zip(dc['SW'], dc['FP'], dc['FN'])], 'ac_feedback_decomposition': ac_audit, 'comparison': {'old_output_cm_v': old_cm, 'new_output_cm_v': new_cm, 'output_cm_delta_v': new_cm - old_cm, 'new_output_cm_error_to_0p9_v': new_cm - 0.9, 'old_1khz_gain': old_gain, 'new_1khz_gain': ac_audit[1]['sensor_to_filter_diff_gain_abs'], 'gain_relative_change': ac_audit[1]['sensor_to_filter_diff_gain_abs'] / old_gain - 1, 'old_NCM_v': float(old_canary_op[5]), 'new_NCM_v': op['XPGA_XOTA_NCM'], 'old_BN_v_from_real_zero_input_node': old_g4_nodes['v(xg4.xdut.xota.bn)'], 'new_BN_v': op['XPGA_XOTA_BN'], 'old_three_dc_diff_v': (old_canary_dc[:, 2] - old_canary_dc[:, 3]).tolist()}, 'legacy_OP_vector_evidence_issue': {'dc_rows': 81, 'device_parameter_columns': 210, 'constant_device_parameter_columns': len(constant_cols), 'same_bias_device_compare_valid': False, 'example_field': old_xmsp_key, 'zero_row_exported_vds_v': old_xmsp_vds, 'zero_row_node_VDD_minus_OUTP_v': old_node_vsd, 'reason': 'run_diagnostic.py did not save MOS parameter sweep vectors; post-sweep @device scalar readings were repeated by wrdata. These cannot establish each-point MOS region or a same-OP comparison.', 'consequence': 'Previously recorded device_regions sweep gate lacks the claimed pointwise evidence. Real DC node waveforms and sampling transient are not thereby invalidated. Preserve originals; do not transfer this gate to school_r1.', 'old_zero_input_node_values': old_g4_nodes}, 'retained_notices': notices, 'formal_stability_gate_pass': False, 'sampled_noise_qualified': False, 'pvt_45_run': False}
    (HERE / 'school_r1_canary_independent_review.json').write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': output['status'], 'comparison': output['comparison'], 'old_mos_sweep_columns_invalid_as_pointwise_evidence': len(constant_cols)}, indent=2))
if __name__ == '__main__':
    main()
