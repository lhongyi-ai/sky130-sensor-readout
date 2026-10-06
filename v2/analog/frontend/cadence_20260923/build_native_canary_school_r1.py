#!/usr/bin/env python3
"""Explicit school-legal proposal; it is a new UNQUALIFIED circuit variant.

All geometry decisions are recorded. Only source model-derived end resistance
and resistance-per-length estimates are used for series resistor allocation;
CDF's displayed resistance is not used. No remote operations or simulations.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'canary_connectivity.json'
MAPPING = HERE / 'native_canary_objects.json'
GRID = Decimal('.005')


def dstr(n):
    return format(n.normalize(), 'f')


def um(n):
    return dstr(n) + 'u'


def main():
    source = json.loads(SOURCE.read_text())
    original = json.loads(MAPPING.read_text())
    refs = {p['path']: p for p in source['primitives']}
    objects, resistor_changes, cap_changes = [], [], []
    internal_nodes = []
    new_standalone_bp = None
    for original_object in original:
        obj = deepcopy(original_object)
        if obj['kind'] == 'resistor':
            ref = refs[obj['originalpath']]
            target = Decimal(str(ref['context_parameters']['R']))
            width, rend, per_um = {
                'res_high_po_0p35': (Decimal('.35'), Decimal('961'), Decimal('993')),
                'res_high_po_0p69': (Decimal('.69'), Decimal('779.8'), Decimal('491.36')),
            }[obj['cell']]
            exact_original_length = (target - rend) / per_um
            count = int((exact_original_length / Decimal(100)).to_integral_value(rounding=ROUND_CEILING)) if target > 100000 else 1
            per_target = target / count
            raw_length = (per_target - rend) / per_um
            quantized_length = (raw_length / GRID).to_integral_value(rounding=ROUND_HALF_UP) * GRID
            assert Decimal('.5') <= quantized_length <= Decimal(100)
            predicted_total = count * (rend + per_um * quantized_length)
            intermediate = [obj['name'] + '_SERIES_NODE_' + str(k).zfill(2)
                            for k in range(1, count)]
            internal_nodes += intermediate
            endpoints = [obj['nets']['PLUS']] + intermediate + [obj['nets']['MINUS']]
            segment_names = []
            for k in range(count):
                part = deepcopy(obj)
                part['name'] = obj['name'] if count == 1 else obj['name'] + '_SEG_' + str(k + 1).zfill(2)
                segment_names.append(part['name'])
                part['props'] = {'segL': um(quantized_length), 'segW': um(width),
                                 'segments': 1, 'connection': 'Series'}
                part['nets'] = {'PLUS': endpoints[k], 'MINUS': endpoints[k + 1], 'B': obj['nets']['B']}
                part['mapping_segment_index'] = k + 1
                part['mapping_segment_count'] = count
                part['mapping_notes'] = [
                    'New school_r1 geometry: source target resistance allocated using model-derived end and per-length estimates, then length rounded to nearest 5nm. Not based on CDF r and not measured resistance.',
                    'Every segment is a separate physical primitive with segments=1; native geometry and connectivity readback required. Added end parasitics and bias dependence are not guaranteed equivalent.',
                ]
                objects.append(part)
                if part['nets']['PLUS'] == 'XPGA_XOTA_BP':
                    new_standalone_bp = part['name'] + '.PLUS'
            resistor_changes.append({
                'originalpath': obj['originalpath'], 'cell': obj['cell'],
                'source_target_ohm': float(target),
                'original_requested_length_um': ref['parameters']['L'],
                'source_estimate_end_ohm': float(rend),
                'source_estimate_ohm_per_um': float(per_um),
                'segment_count': count, 'segment_names': segment_names,
                'internal_nodes': intermediate,
                'each_segment_target_ohm': float(per_target),
                'each_unrounded_length_um': float(raw_length),
                'each_rounded_length_um': float(quantized_length),
                'predicted_total_ohm': float(predicted_total),
                'predicted_delta_ohm': float(predicted_total - target),
                'predicted_relative_delta': float(predicted_total / target - 1),
                'prediction_scope': 'Nominal source-model linear estimate only; not CDF r, measured resistance or parasitic equivalence.',
            })
        elif obj['kind'] == 'mim' and obj['source_parameters']['W'] == 3 and obj['source_parameters']['L'] == 3:
            assert obj['props']['m'] == '4096'
            obj['props']['w'] = obj['props']['l'] = '4u'
            obj['mapping_notes'] = [
                'New school_r1 variant: source 3um x 3um CDAC unit changed to school minimum 4um x 4um. 4096 units per side retained; this increases sampling load and invalidates transfer of candidate06 dynamic/noise qualification.',
                'm=4096 remains pending actual unit/bank AC capacitance and native multiplier verification; no statistical-model or mismatch equivalence claimed.',
            ]
            cap_changes.append({'originalpath': obj['originalpath'], 'source_W_um': 3,
                                'source_L_um': 3, 'school_W_um': 4, 'school_L_um': 4,
                                'm_requested': 4096})
            objects.append(obj)
        else:
            if obj['name'] == 'VDD' and obj['kind'] == 'testbench_source':
                obj['name'] = 'VDD_SRC'
            objects.append(obj)

    byname = {x['name']: x for x in objects}
    assert len(objects) == len(byname) == 133
    assert Counter(x['kind'] for x in objects) == {
        'mos': 55, 'resistor': 36, 'mim': 30,
        'testbench_resistor': 4, 'testbench_source': 8}
    assert len(cap_changes) == 2
    assert len(internal_nodes) == len(set(internal_nodes)) == 14
    terminal_uses = defaultdict(list)
    for obj in objects:
        for pin, node in obj['nets'].items():
            terminal_uses[node].append(obj['name'] + '.' + pin)
        if obj['kind'] == 'mos':
            original_obj = next(x for x in original if x['originalpath'] == obj['originalpath'])
            assert obj == original_obj
        elif obj['kind'] == 'resistor':
            assert obj['nets']['B'] == '0'
            assert set(obj['props']) == {'segL', 'segW', 'segments', 'connection'}
        elif obj['kind'] == 'mim':
            assert obj['nets'] == next(x for x in original if x['originalpath'] == obj['originalpath'])['nets']
    for row in resistor_changes:
        original_obj = next(x for x in original if x['originalpath'] == row['originalpath'])
        parts = [byname[name] for name in row['segment_names']]
        assert parts[0]['nets']['PLUS'] == original_obj['nets']['PLUS']
        assert parts[-1]['nets']['MINUS'] == original_obj['nets']['MINUS']
        for a, b in zip(parts, parts[1:]):
            assert a['nets']['MINUS'] == b['nets']['PLUS']
        for node in row['internal_nodes']:
            assert len(terminal_uses[node]) == 2
        assert all(Decimal(p['props']['segL'][:-1]) % GRID == 0 for p in parts)
    singles = {node: pins for node, pins in terminal_uses.items() if len(pins) == 1}
    assert singles == {'XPGA_XOTA_BP': [new_standalone_bp]}
    original_netnames = {n for x in original for n in x['nets'].values()}
    assert not (set(internal_nodes) & original_netnames)
    assert set(terminal_uses) == original_netnames | set(internal_nodes)
    bp = next(r for r in resistor_changes if r['source_target_ohm'] == 1000000)
    assert bp['segment_count'] == 11

    output = HERE / 'native_canary_school_r1_objects.json'
    output.write_text(json.dumps(objects, indent=2, allow_nan=False) + '\n')
    c_old = Decimal('19.845') * 4096 / 1000
    c_new = Decimal('34.62225') * 4096 / 1000
    assert c_old == Decimal('81.285120') and c_new == Decimal('141.81273600')
    report = {
        'status': 'SCHOOL_R1_NEW_VARIANT_UNQUALIFIED',
        'scope': 'Locally generated mapping proposal after live geometry inventory reported by root. This script does not run Cadence or independently recheck that inventory.',
        'source_connectivity_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'source_native_objects_sha256': hashlib.sha256(MAPPING.read_bytes()).hexdigest(),
        'school_r1_objects_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'object_count': len(objects), 'counts': dict(Counter(x['kind'] for x in objects)),
        'geometry_rules': {'resistor_max_single_length_um': 100, 'resistor_length_grid_um': .005,
                           'rounding': 'Nearest 0.005um; exact half-grid ties ROUND_HALF_UP.',
                           'mim_minimum_W_L_um': 4,
                           'MOS_width_mapping': 'Unchanged: 80=2x40,64=2x32,180=4x45um,all m=1. New parasitics unqualified.'},
        'resistor_mapping': resistor_changes,
        'mim_mapping': cap_changes,
        'sampling_bank_prediction': {
            'units_per_side': 4096, 'original_unit_fF': 19.845,
            'school_4um_unit_fF_basis': 34.62225,
            'original_per_side_pF': float(c_old), 'new_predicted_per_side_pF': float(c_new),
            'delta_per_side_pF': float(c_new - c_old),
            'load_ratio': float(c_new / c_old),
            'scope': 'Arithmetic projection using prior school single-unit value; m4096 scaling, actual AC bank value, noise and dynamics must be measured.'},
        'checks': {'unique_instance_names': True, 'no_generated_net_collision': True,
                   'all_MOS_records_unchanged': True, 'all_series_endpoints_match_source': True,
                   '14_internal_series_nodes_each_degree_two': True,
                   'all_36_resistor_bodies_at_ground': True,
                   'all_resistor_lengths_on_grid_and_in_range': True,
                   '22_original_resistors_preserved_as_36_series_primitives': True,
                   '1Mohm_BP_branch_preserved_with_11_segments': True,
                   'testbench_VDD_source_renamed_only': True},
        'single_terminal_nets': singles,
        'inherited_passes_invalidated': ['candidate06 dynamic sampling/settling qualification',
                                       'candidate06 static noise characterization as this new circuit result',
                                       'any claim of equal MOS diffusion geometry or resistor parasitics'],
        'cadence_executed_by_this_script': False,
        'formal_stability_gate_pass': False,
        'sampled_noise_qualified': False,
        'pvt_45_run': False,
    }
    (HERE / 'native_canary_school_r1_mapping_review.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'object_count', 'counts', 'sampling_bank_prediction', 'single_terminal_nets')}, indent=2))


if __name__ == '__main__':
    main()
