#!/usr/bin/env python3
"""Audit nominal static CDAC linearity from the frozen routed SKY130 RC PEX.

This script does not alter or regenerate the physical design.  It contracts
every finite interconnect resistor for the infinite-settling-time limit, keeps
all extracted capacitors (including values written with ``p`` suffixes), adds
the qualified nominal capacitance of each 3 um x 3 um SKY130 MIM device, and
then applies top-plate charge conservation for every 12-bit code.

The result is intentionally scoped to the passive CDAC.  Interconnect R is
retained for connectivity checks but belongs in a later dynamic-settling
analysis, not in static INL/DNL.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
from typing import Iterable


HERE = Path(__file__).resolve().parent
V2 = HERE.parents[2]
ROUTE = V2 / "physical" / "cdac_route_20260911"
ARTIFACTS = ROUTE / "artifacts"
RESULTS = HERE / "results"

TOP_PEX = ARTIFACTS / "cdac_diff_routed_flat_rc.spice"
SIDE_P_PEX = ARTIFACTS / "cdac_side_p_routed_flat.rc.spice"
SIDE_N_PEX = ARTIFACTS / "cdac_side_n_routed_flat.rc.spice"
DEVICE_QUALIFICATION = V2 / "environment" / "results" / "device_qualification.json"
ROUTE_QUALIFICATION = ROUTE / "qualification.json"
TEST_SOURCE = HERE / "test_cdac_pex_linearity.py"

EXPECTED_TOP_PORTS = [
    *(f"P_{name}" for name in ["TOP", *(f"B{i}" for i in range(11, -1, -1)), "DUMMY", "EDGE_BIAS"]),
    *(f"N_{name}" for name in ["TOP", *(f"B{i}" for i in range(11, -1, -1)), "DUMMY", "EDGE_BIAS"]),
]
EXPECTED_SIDE_PORTS = ["TOP", *(f"B{i}" for i in range(11, -1, -1)), "DUMMY", "EDGE_BIAS"]
REFERENCE_STEP_V = 0.4  # 1.1 V - 0.7 V
ADC_INL_LIMIT_LSB = 1.5
ADC_DNL_MIN_LSB = -0.9
ADC_DNL_MAX_LSB = 1.5


SUFFIX_SCALE = {
    "": 1.0,
    "a": 1e-18,
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "g": 1e9,
    "t": 1e12,
}


def parse_spice_number(token: str) -> float:
    """Parse the value forms used by the frozen Magic-generated netlists."""

    match = re.fullmatch(
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)(meg|[afpnumkgt]?)",
        token.strip().lower(),
    )
    if not match:
        raise ValueError(f"Unsupported SPICE number: {token!r}")
    return float(match.group(1)) * SUFFIX_SCALE[match.group(2)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


@dataclass(frozen=True)
class PairCapacitance:
    extracted_f: float = 0.0
    intrinsic_f: float = 0.0
    extracted_elements: int = 0
    intrinsic_devices: int = 0

    @property
    def total_f(self) -> float:
        return self.extracted_f + self.intrinsic_f


@dataclass
class ParsedNetwork:
    path: Path
    ports: list[str]
    intrinsic_unit_f: float
    pairs: dict[tuple[str, str], PairCapacitance]
    resistor_count: int
    resistor_sum_ohm: float
    largest_resistor_ohm: float
    extracted_cap_count: int
    positive_extracted_cap_count: int
    zero_extracted_cap_count: int
    extracted_suffix_counts: dict[str, int]
    mim_count: int
    collapsed_mim_count: int
    node_count: int
    component_count: int
    orphan_components: list[list[str]]
    port_collisions: list[list[str]]

    def pair(self, left: str, right: str) -> PairCapacitance:
        return self.pairs.get(tuple(sorted((left, right))), PairCapacitance())

    def incident(self, node: str) -> dict[str, PairCapacitance]:
        result: dict[str, PairCapacitance] = {}
        for (left, right), value in self.pairs.items():
            if left == node:
                result[right] = value
            elif right == node:
                result[left] = value
        return result


def read_subckt_ports(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if not line.lower().startswith(".subckt "):
            continue
        ports = line.split()[2:]
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].lstrip().startswith("+"):
            ports.extend(lines[cursor].split()[1:])
            cursor += 1
        return ports
    raise ValueError("No .subckt declaration found")


def _updated_pair(
    old: PairCapacitance,
    *,
    extracted_f: float = 0.0,
    intrinsic_f: float = 0.0,
    extracted_elements: int = 0,
    intrinsic_devices: int = 0,
) -> PairCapacitance:
    return PairCapacitance(
        extracted_f=old.extracted_f + extracted_f,
        intrinsic_f=old.intrinsic_f + intrinsic_f,
        extracted_elements=old.extracted_elements + extracted_elements,
        intrinsic_devices=old.intrinsic_devices + intrinsic_devices,
    )


def parse_pex(path: Path, intrinsic_unit_f: float) -> ParsedNetwork:
    lines = path.read_text().splitlines()
    ports = read_subckt_ports(lines)
    uf = UnionFind()
    nodes = set(ports)
    resistors: list[float] = []

    for line in lines:
        tokens = line.split()
        if not tokens or not tokens[0].upper().startswith("R"):
            continue
        if len(tokens) != 4:
            raise ValueError(f"Unexpected resistor syntax in {path}: {line}")
        left, right = tokens[1:3]
        value = parse_spice_number(tokens[3])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Non-positive resistor in {path}: {line}")
        nodes.update((left, right))
        uf.union(left, right)
        resistors.append(value)

    # VSUBS is the fixed substrate node generated by Magic.  It is not a
    # subcircuit port in these files, so add it explicitly as a named component.
    named_nodes = [*ports, "VSUBS"]
    for node in named_nodes:
        nodes.add(node)
        uf.find(node)

    root_to_names: dict[str, list[str]] = {}
    for node in named_nodes:
        root_to_names.setdefault(uf.find(node), []).append(node)
    port_collisions = [names for names in root_to_names.values() if len(names) > 1]

    pairs: dict[tuple[str, str], PairCapacitance] = {}
    extracted_cap_count = 0
    positive_extracted_cap_count = 0
    zero_extracted_cap_count = 0
    extracted_suffix_counts: dict[str, int] = {}
    mim_count = 0
    collapsed_mim_count = 0

    def component_name(node: str) -> str:
        root = uf.find(node)
        names = root_to_names.get(root, [])
        if len(names) != 1:
            if not names:
                return f"__FLOATING__:{root}"
            return f"__COLLISION__:{'|'.join(sorted(names))}"
        return names[0]

    def add_pair(
        left: str,
        right: str,
        *,
        extracted_f: float = 0.0,
        intrinsic_f: float = 0.0,
        extracted_elements: int = 0,
        intrinsic_devices: int = 0,
    ) -> bool:
        left_name = component_name(left)
        right_name = component_name(right)
        if left_name == right_name:
            return False
        key = tuple(sorted((left_name, right_name)))
        pairs[key] = _updated_pair(
            pairs.get(key, PairCapacitance()),
            extracted_f=extracted_f,
            intrinsic_f=intrinsic_f,
            extracted_elements=extracted_elements,
            intrinsic_devices=intrinsic_devices,
        )
        return True

    for line in lines:
        tokens = line.split()
        if not tokens:
            continue
        designator = tokens[0][0].upper()
        if designator == "C" and not tokens[0].startswith("."):
            if len(tokens) != 4:
                raise ValueError(f"Unexpected capacitor syntax in {path}: {line}")
            value = parse_spice_number(tokens[3])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Negative/non-finite capacitor in {path}: {line}")
            suffix_match = re.search(r"(meg|[afpnumkgt])$", tokens[3].lower())
            suffix = suffix_match.group(1) if suffix_match else "none"
            extracted_suffix_counts[suffix] = extracted_suffix_counts.get(suffix, 0) + 1
            extracted_cap_count += 1
            if value == 0:
                zero_extracted_cap_count += 1
            else:
                positive_extracted_cap_count += 1
            nodes.update(tokens[1:3])
            add_pair(tokens[1], tokens[2], extracted_f=value, extracted_elements=1)
        elif designator == "X" and "sky130_fd_pr__cap_mim_m3_1" in tokens:
            if len(tokens) < 6:
                raise ValueError(f"Unexpected MIM syntax in {path}: {line}")
            parameters = {part.split("=", 1)[0].lower(): part.split("=", 1)[1] for part in tokens if "=" in part}
            if parse_spice_number(parameters.get("l", "nan")) != 3 or parse_spice_number(parameters.get("w", "nan")) != 3:
                raise ValueError(f"Non-3um MIM found in {path}: {line}")
            mim_count += 1
            nodes.update(tokens[1:3])
            if not add_pair(tokens[1], tokens[2], intrinsic_f=intrinsic_unit_f, intrinsic_devices=1):
                collapsed_mim_count += 1

    # Every routed metal component must reach exactly one declared port or the
    # substrate.  A capacitor-only floating island would need Schur elimination
    # and is rejected here rather than silently discarded.
    components: dict[str, list[str]] = {}
    for node in nodes:
        components.setdefault(uf.find(node), []).append(node)
    named_roots = set(root_to_names)
    orphan_components = [sorted(members) for root, members in components.items() if root not in named_roots]

    return ParsedNetwork(
        path=path,
        ports=ports,
        intrinsic_unit_f=intrinsic_unit_f,
        pairs=pairs,
        resistor_count=len(resistors),
        resistor_sum_ohm=sum(resistors),
        largest_resistor_ohm=max(resistors, default=0.0),
        extracted_cap_count=extracted_cap_count,
        positive_extracted_cap_count=positive_extracted_cap_count,
        zero_extracted_cap_count=zero_extracted_cap_count,
        extracted_suffix_counts=dict(sorted(extracted_suffix_counts.items())),
        mim_count=mim_count,
        collapsed_mim_count=collapsed_mim_count,
        node_count=len(nodes),
        component_count=len(components),
        orphan_components=orphan_components,
        port_collisions=port_collisions,
    )


def load_intrinsic_unit_capacitance() -> tuple[float, dict[str, object]]:
    evidence = json.loads(DEVICE_QUALIFICATION.read_text())
    nominal_rows = [
        row
        for row in evidence["runs"]
        if row["name"] == "pvt/tt_1.80_27" and row["corner"] == "tt"
    ]
    if len(nominal_rows) != 1:
        raise ValueError("Could not identify one nominal MIM qualification row")
    value = float(nominal_rows[0]["cap_a"])
    if evidence["status"] != "OPEN_DEVICE_ENVIRONMENT_PASS" or not math.isclose(value, 19.845e-15, rel_tol=1e-12):
        raise ValueError("Frozen MIM capacitance evidence is not qualified")
    return value, {
        "value_f": value,
        "source": str(DEVICE_QUALIFICATION.relative_to(V2)),
        "source_sha256": sha256(DEVICE_QUALIFICATION),
        "source_status": evidence["status"],
        "measurement": "ngspice AC, SKY130 3um x 3um MIM, TT 1.8V 27C",
    }


def side_capacitances(network: ParsedNetwork, side: str) -> dict[str, object]:
    prefix = f"{side}_" if side else ""
    top = prefix + "TOP"
    incident = network.incident(top)
    expected_others = [
        *(prefix + f"B{i}" for i in range(11, -1, -1)),
        prefix + "DUMMY",
        prefix + "EDGE_BIAS",
        "VSUBS",
    ]
    missing = [node for node in expected_others if node not in incident]
    unexpected = sorted(set(incident) - set(expected_others))
    total_f = sum(value.total_f for value in incident.values())
    bit_total_f = {
        f"B{i}": incident[prefix + f"B{i}"].total_f for i in range(12)
    }
    bit_extracted_f = {
        f"B{i}": incident[prefix + f"B{i}"].extracted_f for i in range(12)
    }
    bit_intrinsic_f = {
        f"B{i}": incident[prefix + f"B{i}"].intrinsic_f for i in range(12)
    }
    return {
        "top": top,
        "total_f": total_f,
        "bit_total_f": bit_total_f,
        "bit_extracted_f": bit_extracted_f,
        "bit_intrinsic_f": bit_intrinsic_f,
        "dummy_total_f": incident[prefix + "DUMMY"].total_f,
        "edge_bias_total_f": incident[prefix + "EDGE_BIAS"].total_f,
        "substrate_total_f": incident["VSUBS"].total_f,
        "missing_expected_incident_nodes": missing,
        "unexpected_incident_nodes": unexpected,
    }


def code_values_from_weights(weights_lsb_first: list[float]) -> list[float]:
    return [
        sum(weight for bit, weight in enumerate(weights_lsb_first) if code & (1 << bit))
        for code in range(4096)
    ]


def endpoint_metrics(values: list[float]) -> dict[str, object]:
    if len(values) != 4096:
        raise ValueError("Expected exactly 4096 code values")
    endpoint_lsb = (values[-1] - values[0]) / 4095
    if endpoint_lsb <= 0:
        raise ValueError("Non-positive endpoint LSB")
    steps = [values[index + 1] - values[index] for index in range(4095)]
    dnl = [step / endpoint_lsb - 1 for step in steps]
    inl = [
        (value - (values[0] + code * endpoint_lsb)) / endpoint_lsb
        for code, value in enumerate(values)
    ]
    nonpositive = [index for index, step in enumerate(steps) if step <= 0]
    below_missing_code_condition = [index for index, value in enumerate(dnl) if value <= -1]
    return {
        "endpoint_lsb": endpoint_lsb,
        "span": values[-1] - values[0],
        "min_dnl_lsb": min(dnl),
        "max_dnl_lsb": max(dnl),
        "min_inl_lsb": min(inl),
        "max_inl_lsb": max(inl),
        "max_abs_inl_lsb": max(abs(value) for value in inl),
        "min_step": min(steps),
        "max_step": max(steps),
        "worst_min_dnl_transition": int(min(range(4095), key=dnl.__getitem__)),
        "worst_max_abs_inl_code": int(max(range(4096), key=lambda index: abs(inl[index]))),
        "nonpositive_transition_count": len(nonpositive),
        "nonpositive_transition_first_20": nonpositive[:20],
        "dnl_le_minus_one_count": len(below_missing_code_condition),
        "monotonic": not nonpositive,
        "missing_code_free_condition": not below_missing_code_condition,
        "inl": inl,
        "dnl": dnl,
        "steps": steps,
    }


def scalar_metrics(metrics: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in metrics.items() if key not in {"inl", "dnl", "steps"}}


def write_pair_csv(network: ParsedNetwork) -> Path:
    path = RESULTS / "capacitance_pairs.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "node_a",
                "node_b",
                "extracted_cap_fF",
                "intrinsic_mim_cap_fF",
                "total_cap_fF",
                "extracted_element_count",
                "intrinsic_mim_device_count",
            ]
        )
        for (left, right), value in sorted(network.pairs.items()):
            writer.writerow(
                [
                    left,
                    right,
                    f"{value.extracted_f / 1e-15:.12g}",
                    f"{value.intrinsic_f / 1e-15:.12g}",
                    f"{value.total_f / 1e-15:.12g}",
                    value.extracted_elements,
                    value.intrinsic_devices,
                ]
            )
    return path


def write_matrix_csv(network: ParsedNetwork) -> Path:
    path = RESULTS / "port_capacitance_matrix_fF.csv"
    nodes = [*network.ports, "VSUBS"]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["node", *nodes])
        for left in nodes:
            writer.writerow(
                [
                    left,
                    *(f"{network.pair(left, right).total_f / 1e-15:.12g}" if left != right else "0" for right in nodes),
                ]
            )
    return path


def write_bit_csv(side_results: dict[str, dict[str, object]], intrinsic_unit_f: float) -> Path:
    path = RESULTS / "bit_weights.csv"
    with path.open("w", newline="") as handle:
        fields = [
            "side",
            "bit",
            "binary_unit_count",
            "intrinsic_mim_cap_fF",
            "extracted_top_coupling_fF",
            "effective_top_coupling_fF",
            "fraction_of_top_total",
            "endpoint_weight_lsb",
            "ideal_weight_lsb",
            "weight_error_lsb",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for side in ("P", "N"):
            result = side_results[side]
            active_sum_f = sum(result["bit_total_f"].values())
            endpoint_cap_lsb = active_sum_f / 4095
            for bit in range(12):
                name = f"B{bit}"
                total_f = result["bit_total_f"][name]
                weight_lsb = total_f / endpoint_cap_lsb
                writer.writerow(
                    {
                        "side": side,
                        "bit": name,
                        "binary_unit_count": 1 << bit,
                        "intrinsic_mim_cap_fF": f"{result['bit_intrinsic_f'][name] / 1e-15:.12g}",
                        "extracted_top_coupling_fF": f"{result['bit_extracted_f'][name] / 1e-15:.12g}",
                        "effective_top_coupling_fF": f"{total_f / 1e-15:.12g}",
                        "fraction_of_top_total": f"{total_f / result['total_f']:.15g}",
                        "endpoint_weight_lsb": f"{weight_lsb:.15g}",
                        "ideal_weight_lsb": 1 << bit,
                        "weight_error_lsb": f"{weight_lsb - (1 << bit):.15g}",
                    }
                )
    return path


def write_codes_csv(
    p_values_v: list[float],
    n_values_v: list[float],
    diff_values_v: list[float],
    p_metrics: dict[str, object],
    n_metrics: dict[str, object],
    diff_metrics: dict[str, object],
) -> Path:
    path = RESULTS / "all_4096_codes.csv"
    n_full_v = n_values_v[-1]
    with path.open("w", newline="") as handle:
        fields = [
            "code",
            "p_top_delta_v",
            "n_top_equivalent_delta_v",
            "n_top_complement_delta_v",
            "differential_output_v",
            "p_inl_lsb",
            "n_inl_lsb",
            "differential_inl_lsb",
            "p_dnl_to_next_lsb",
            "n_dnl_to_next_lsb",
            "differential_dnl_to_next_lsb",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for code in range(4096):
            writer.writerow(
                {
                    "code": code,
                    "p_top_delta_v": f"{p_values_v[code]:.15g}",
                    "n_top_equivalent_delta_v": f"{n_values_v[code]:.15g}",
                    "n_top_complement_delta_v": f"{n_full_v - n_values_v[code]:.15g}",
                    "differential_output_v": f"{diff_values_v[code]:.15g}",
                    "p_inl_lsb": f"{p_metrics['inl'][code]:.15g}",
                    "n_inl_lsb": f"{n_metrics['inl'][code]:.15g}",
                    "differential_inl_lsb": f"{diff_metrics['inl'][code]:.15g}",
                    "p_dnl_to_next_lsb": f"{p_metrics['dnl'][code]:.15g}" if code < 4095 else "",
                    "n_dnl_to_next_lsb": f"{n_metrics['dnl'][code]:.15g}" if code < 4095 else "",
                    "differential_dnl_to_next_lsb": f"{diff_metrics['dnl'][code]:.15g}" if code < 4095 else "",
                }
            )
    return path


def plot_linearity(
    p_metrics: dict[str, object],
    n_metrics: dict[str, object],
    diff_metrics: dict[str, object],
) -> Path:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/sky130_cdac_pex_mplconfig")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = RESULTS / "static_linearity.png"
    codes = range(4096)
    transitions = range(4095)
    fig, axes = plt.subplots(2, 1, figsize=(11.0, 8.5), dpi=180, layout="constrained")
    fig.suptitle("Routed SKY130 CDAC — nominal static PEX linearity", fontsize=15, y=1.02)

    axes[0].plot(codes, p_metrics["inl"], color="#3b82f6", linewidth=1.0, label="P side")
    axes[0].plot(codes, n_metrics["inl"], color="#f59e0b", linewidth=1.0, label="N side")
    axes[0].plot(codes, diff_metrics["inl"], color="#111827", linewidth=1.2, label="Differential")
    axes[0].axhline(ADC_INL_LIMIT_LSB, color="#dc2626", linewidth=0.8, linestyle="--", label="Target ±1.5 LSB")
    axes[0].axhline(-ADC_INL_LIMIT_LSB, color="#dc2626", linewidth=0.8, linestyle="--")
    axes[0].set_ylabel("Endpoint INL (LSB)")
    axes[0].set_xlim(0, 4095)
    axes[0].grid(True, color="#e5e7eb", linewidth=0.6)
    axes[0].legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=4, frameon=False)

    axes[1].plot(transitions, diff_metrics["dnl"], color="#2563eb", linewidth=0.65, label="Differential DNL")
    axes[1].axhline(ADC_DNL_MIN_LSB, color="#dc2626", linewidth=0.9, linestyle="--", label="Target −0.9 / +1.5 LSB")
    axes[1].axhline(ADC_DNL_MAX_LSB, color="#dc2626", linewidth=0.9, linestyle="--")
    axes[1].set_xlabel("Code before transition")
    axes[1].set_ylabel("Endpoint DNL (LSB)")
    axes[1].set_xlim(0, 4094)
    axes[1].grid(True, color="#e5e7eb", linewidth=0.6)
    axes[1].legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, frameon=False)

    fig.savefig(path, bbox_inches="tight", pad_inches=0.20)
    plt.close(fig)
    return path


def plot_bit_errors(side_results: dict[str, dict[str, object]]) -> Path:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/sky130_cdac_pex_mplconfig")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = RESULTS / "bit_weight_error.png"
    bits = list(range(12))
    p_sum = sum(side_results["P"]["bit_total_f"].values())
    n_sum = sum(side_results["N"]["bit_total_f"].values())
    p_lsb = p_sum / 4095
    n_lsb = n_sum / 4095
    p_error = [side_results["P"]["bit_total_f"][f"B{bit}"] / p_lsb - (1 << bit) for bit in bits]
    n_error = [side_results["N"]["bit_total_f"][f"B{bit}"] / n_lsb - (1 << bit) for bit in bits]

    fig, ax = plt.subplots(figsize=(11.0, 5.7), dpi=180, layout="constrained")
    fig.suptitle("Effective bit-weight error after routed-capacitance extraction", fontsize=15, y=1.03)
    width = 0.38
    ax.bar([bit - width / 2 for bit in bits], p_error, width=width, color="#3b82f6", label="P side")
    ax.bar([bit + width / 2 for bit in bits], n_error, width=width, color="#f59e0b", label="N side")
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_xticks(bits, [f"B{bit}" for bit in bits])
    ax.set_xlabel("Physical switch port")
    ax.set_ylabel("Error from ideal binary weight (endpoint LSB)")
    ax.grid(True, axis="y", color="#e5e7eb", linewidth=0.6)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, frameon=False)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.20)
    plt.close(fig)
    return path


def network_summary(network: ParsedNetwork) -> dict[str, object]:
    cross_side_pairs = [
        [left, right]
        for left, right in network.pairs
        if (left.startswith("P_") and right.startswith("N_"))
        or (left.startswith("N_") and right.startswith("P_"))
    ]
    return {
        "file": str(network.path.relative_to(V2)),
        "sha256": sha256(network.path),
        "ports": network.ports,
        "port_count": len(network.ports),
        "node_count": network.node_count,
        "resistor_contracted_component_count": network.component_count,
        "resistor_count": network.resistor_count,
        "resistor_sum_ohm_non_path_metric": network.resistor_sum_ohm,
        "largest_resistor_segment_ohm": network.largest_resistor_ohm,
        "extracted_cap_element_count_including_zero": network.extracted_cap_count,
        "positive_extracted_cap_element_count": network.positive_extracted_cap_count,
        "zero_extracted_cap_element_count": network.zero_extracted_cap_count,
        "extracted_cap_suffix_counts": network.extracted_suffix_counts,
        "mim_device_count": network.mim_count,
        "same_net_edge_mim_count_excluded_from_transfer": network.collapsed_mim_count,
        "orphan_component_count": len(network.orphan_components),
        "orphan_components_first_10": network.orphan_components[:10],
        "port_collisions": network.port_collisions,
        "cross_side_capacitor_pair_count": len(cross_side_pairs),
        "cross_side_capacitor_pairs": cross_side_pairs,
    }


def side_summary(result: dict[str, object], metrics: dict[str, object]) -> dict[str, object]:
    return {
        "top_total_cap_fF": result["total_f"] / 1e-15,
        "active_bit_cap_sum_fF": sum(result["bit_total_f"].values()) / 1e-15,
        "dummy_to_top_cap_fF": result["dummy_total_f"] / 1e-15,
        "edge_bias_to_top_cap_fF": result["edge_bias_total_f"] / 1e-15,
        "substrate_to_top_cap_fF": result["substrate_total_f"] / 1e-15,
        "static_code_span_v_for_0p4V_reference_step": metrics["span"],
        **scalar_metrics(metrics),
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    intrinsic_unit_f, intrinsic_evidence = load_intrinsic_unit_capacitance()
    top = parse_pex(TOP_PEX, intrinsic_unit_f)
    side_p = parse_pex(SIDE_P_PEX, intrinsic_unit_f)
    side_n = parse_pex(SIDE_N_PEX, intrinsic_unit_f)

    p_result = side_capacitances(top, "P")
    n_result = side_capacitances(top, "N")
    standalone_p_result = side_capacitances(side_p, "")
    standalone_n_result = side_capacitances(side_n, "")

    p_weights = [p_result["bit_total_f"][f"B{i}"] / p_result["total_f"] for i in range(12)]
    n_weights = [n_result["bit_total_f"][f"B{i}"] / n_result["total_f"] for i in range(12)]
    p_values_v = [REFERENCE_STEP_V * value for value in code_values_from_weights(p_weights)]
    n_values_v = [REFERENCE_STEP_V * value for value in code_values_from_weights(n_weights)]
    n_full_v = n_values_v[-1]
    diff_values_v = [p_values_v[code] - (n_full_v - n_values_v[code]) for code in range(4096)]

    p_metrics = endpoint_metrics(p_values_v)
    n_metrics = endpoint_metrics(n_values_v)
    diff_metrics = endpoint_metrics(diff_values_v)

    p_normalized = [(value - p_values_v[0]) / (p_values_v[-1] - p_values_v[0]) for value in p_values_v]
    n_normalized = [(value - n_values_v[0]) / (n_values_v[-1] - n_values_v[0]) for value in n_values_v]
    max_pn_endpoint_difference_lsb = max(abs(p - n) for p, n in zip(p_normalized, n_normalized)) * 4095

    pair_csv = write_pair_csv(top)
    matrix_csv = write_matrix_csv(top)
    bit_csv = write_bit_csv({"P": p_result, "N": n_result}, intrinsic_unit_f)
    codes_csv = write_codes_csv(p_values_v, n_values_v, diff_values_v, p_metrics, n_metrics, diff_metrics)
    linearity_plot = plot_linearity(p_metrics, n_metrics, diff_metrics)
    bit_plot = plot_bit_errors({"P": p_result, "N": n_result})

    side_top_match = {
        "P": {
            "all_code_driving_top_couplings_exact": all(
                p_result["bit_total_f"][f"B{i}"] == standalone_p_result["bit_total_f"][f"B{i}"]
                for i in range(12)
            ),
            "top_total_difference_fF": (p_result["total_f"] - standalone_p_result["total_f"]) / 1e-15,
        },
        "N": {
            "all_code_driving_top_couplings_exact": all(
                n_result["bit_total_f"][f"B{i}"] == standalone_n_result["bit_total_f"][f"B{i}"]
                for i in range(12)
            ),
            "top_total_difference_fF": (n_result["total_f"] - standalone_n_result["total_f"]) / 1e-15,
        },
    }

    ideal_single_side_span_v = REFERENCE_STEP_V * 4095 / 4096
    ideal_diff_span_v = 2 * ideal_single_side_span_v
    gates = {
        "top_ports_are_exactly_the_expected_30": top.ports == EXPECTED_TOP_PORTS,
        "side_ports_are_exactly_the_expected_15": side_p.ports == EXPECTED_SIDE_PORTS and side_n.ports == EXPECTED_SIDE_PORTS,
        "top_has_8712_mim_devices": top.mim_count == 8712,
        "top_has_26210_resistor_segments": top.resistor_count == 26210,
        "all_resistive_nodes_resolve_to_one_named_port_or_substrate": not top.orphan_components and not top.port_collisions,
        "all_expected_top_incident_nodes_present": not p_result["missing_expected_incident_nodes"] and not n_result["missing_expected_incident_nodes"],
        "no_unexpected_top_incident_nodes": not p_result["unexpected_incident_nodes"] and not n_result["unexpected_incident_nodes"],
        "no_extracted_cross_side_capacitor_pair": network_summary(top)["cross_side_capacitor_pair_count"] == 0,
        "standalone_side_code_couplings_match_differential_top": side_top_match["P"]["all_code_driving_top_couplings_exact"] and side_top_match["N"]["all_code_driving_top_couplings_exact"],
        "all_4096_codes_evaluated": len(diff_values_v) == 4096,
        "differential_inl_within_target": diff_metrics["max_abs_inl_lsb"] <= ADC_INL_LIMIT_LSB,
        "differential_dnl_within_target": ADC_DNL_MIN_LSB <= diff_metrics["min_dnl_lsb"] and diff_metrics["max_dnl_lsb"] <= ADC_DNL_MAX_LSB,
        "differential_monotonic": diff_metrics["monotonic"],
        "differential_missing_code_free_condition": diff_metrics["missing_code_free_condition"],
    }
    analysis_integrity_keys = [
        "top_ports_are_exactly_the_expected_30",
        "side_ports_are_exactly_the_expected_15",
        "top_has_8712_mim_devices",
        "top_has_26210_resistor_segments",
        "all_resistive_nodes_resolve_to_one_named_port_or_substrate",
        "all_expected_top_incident_nodes_present",
        "no_unexpected_top_incident_nodes",
        "no_extracted_cross_side_capacitor_pair",
        "standalone_side_code_couplings_match_differential_top",
        "all_4096_codes_evaluated",
    ]
    analysis_valid = all(gates[key] for key in analysis_integrity_keys)
    linearity_pass = all(
        gates[key]
        for key in (
            "differential_inl_within_target",
            "differential_dnl_within_target",
            "differential_monotonic",
            "differential_missing_code_free_condition",
        )
    )
    status = (
        "CDAC_PEX_STATIC_LINEARITY_PASS"
        if analysis_valid and linearity_pass
        else "CDAC_PEX_STATIC_LINEARITY_FAIL_NONMONOTONIC"
        if analysis_valid
        else "CDAC_PEX_STATIC_ANALYSIS_INVALID"
    )

    output_files = [pair_csv, matrix_csv, bit_csv, codes_csv, linearity_plot, bit_plot]
    report = {
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "Nominal passive differential CDAC static charge-redistribution analysis from the final flattened SKY130 routed RC PEX",
        "analysis_valid": analysis_valid,
        "linearity_pass": linearity_pass,
        "cadence_used": False,
        "foundry_signoff": False,
        "complete_adc_qualified": False,
        "post_layout_dynamic_settling_qualified": False,
        "mismatch_or_process_corners_included": False,
        "method": {
            "static_limit": "All finite interconnect resistors are contracted after their connectivity is audited; this is the exact infinite-settling-time topology for the linear passive network.",
            "charge_equation": "Delta(V_TOP) = sum(C_TOP,j * Delta(V_j)) / sum(C_TOP,j), with TOP charge conserved and B11..B0 driven by ideal reference switches.",
            "differential_sequence": "P uses the requested code; N uses its 12-bit complement. DUMMY and EDGE_BIAS remain fixed. The sign convention makes output increase with code.",
            "reference_step_v": REFERENCE_STEP_V,
            "endpoint_definition": "4096 codes, 4095 adjacent transitions; endpoint LSB = (output[4095]-output[0])/4095; DNL = step/endpoint_LSB-1; INL = deviation from endpoint line in endpoint LSB.",
            "intrinsic_mim": intrinsic_evidence,
            "resistor_boundary": "Interconnect R affects finite-time reference settling and cannot change the infinite-time static capacitor ratios. Dynamic RC behavior is explicitly not claimed here.",
        },
        "inputs": {
            "differential_top": network_summary(top),
            "standalone_p": network_summary(side_p),
            "standalone_n": network_summary(side_n),
            "route_qualification": {
                "file": str(ROUTE_QUALIFICATION.relative_to(V2)),
                "sha256": sha256(ROUTE_QUALIFICATION),
                "status": json.loads(ROUTE_QUALIFICATION.read_text())["status"],
            },
            "note_on_cap_counts": "The PEX contains 17710 positive f-suffix capacitors, 20 positive p-suffix capacitors, and two explicit zero-valued coupling entries. This analysis parses every suffix; the earlier routing summary's f-only count is not reused as the matrix.",
        },
        "cross_checks": {
            "standalone_side_vs_top": side_top_match,
            "max_p_vs_n_endpoint_normalized_difference_lsb": max_pn_endpoint_difference_lsb,
        },
        "targets": {
            "max_abs_inl_lsb": ADC_INL_LIMIT_LSB,
            "dnl_lsb_range": [ADC_DNL_MIN_LSB, ADC_DNL_MAX_LSB],
            "monotonic_required": True,
            "missing_code_free_condition_required": True,
        },
        "gates": gates,
        "results": {
            "P": side_summary(p_result, p_metrics),
            "N": side_summary(n_result, n_metrics),
            "differential": {
                **scalar_metrics(diff_metrics),
                "ideal_differential_code_span_v_without_parasitics": ideal_diff_span_v,
                "extracted_differential_code_span_v": diff_metrics["span"],
                "static_span_ratio_to_ideal": diff_metrics["span"] / ideal_diff_span_v,
            },
        },
        "interpretation": {
            "physical_finding": "The extracted lower-bit top-plate couplings are not binary enough. In particular, the B4 transition cannot cover the sum of B3..B0 at every 0xF-to-0x0 carry, and the largest reversal occurs at 2047-to-2048.",
            "nonpositive_transition_count": diff_metrics["nonpositive_transition_count"],
            "missing_code_language": "DNL <= -1 is a failed no-missing-code condition for this DAC transfer. It is not a measured count of final ADC output codes, because comparator, switches, noise, timing, and SAR integration are absent.",
            "corrective_direction": "Rebalance physical bit weights or add a redundant/trimmed CDAC architecture, then reroute and repeat DRC/LVS/PEX before any full-ADC linearity claim.",
        },
        "artifacts": {
            str(path.relative_to(HERE)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in output_files
        },
        "source": {
            "file": "analyze.py",
            "sha256": sha256(Path(__file__)),
            "test_file": TEST_SOURCE.name,
            "test_sha256": sha256(TEST_SOURCE),
            "python": platform.python_version(),
        },
        "limitations": [
            "This is nominal static passive-CDAC analysis, not a full SAR ADC simulation or pass.",
            "The PDK-qualified nominal 3um MIM value is used for every intrinsic device; device mismatch, gradients, voltage coefficients, process corners, and temperature are not included.",
            "Bottom reference nodes are ideal voltage sources. Reference resistance, droop, switch resistance, and the extracted interconnect R require a separate dynamic settling analysis.",
            "Magic's extracted capacitance set is used as provided; no coupling-corner or foundry/Cadence signoff is implied.",
            "DUMMY and EDGE_BIAS are fixed in the code sweep. Their capacitance loads TOP and changes gain, but does not create code steps under that interface contract.",
        ],
    }
    (HERE / "qualification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": status,
                "analysis_valid": analysis_valid,
                "linearity_pass": linearity_pass,
                "differential": scalar_metrics(diff_metrics),
                "max_pn_endpoint_difference_lsb": max_pn_endpoint_difference_lsb,
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0 if analysis_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
