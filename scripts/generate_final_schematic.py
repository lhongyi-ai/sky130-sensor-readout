#!/usr/bin/env python3
"""Render the frozen Day 3 OTA as a reviewable vector schematic.

The figure deliberately separates the OTA core from the external nominal and
loop-gain benches.  It is a documentation drawing; the Xschem source and the
canonical SPICE subcircuit remain the connectivity-authoritative artifacts.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "plots"

INK = "#172033"
MUTED = "#596579"
BLUE = "#1f6feb"
BLUE_DARK = "#124ca0"
TEAL = "#058c86"
ORANGE = "#d97706"
RED = "#c2413b"
GREEN = "#2a8f55"
CORE_BG = "#f5f9ff"
BIAS_BG = "#f4fbf8"
TB_BG = "#fff9ef"


def line(ax, xs, ys, *, color=INK, lw=1.65, ls="-", zorder=2):
    ax.plot(xs, ys, color=color, lw=lw, ls=ls, solid_capstyle="round", zorder=zorder)


def node(ax, x, y, *, color=INK):
    ax.add_patch(Circle((x, y), 0.06, facecolor=color, edgecolor="none", zorder=5))


def net_label(ax, x, y, text, *, color=BLUE_DARK, ha="left", va="bottom", size=8.5):
    ax.text(x, y, text, color=color, fontsize=size, weight="bold", ha=ha, va=va, zorder=6)


def mos(ax, x, y, kind, name, size, *, note="", label_side="right", label_xy=None, label_ha=None):
    """Draw a four-terminal vertical MOS symbol with top/bottom power flow."""
    h = 0.64
    channel_x = x + 0.14
    gate_x = x - 0.34
    color = TEAL if kind == "n" else BLUE
    # Drain/source leads and channel.
    line(ax, [channel_x, channel_x], [y + h, y + 0.31], color=color, lw=2.0)
    line(ax, [channel_x, channel_x], [y - 0.31, y - h], color=color, lw=2.0)
    line(ax, [channel_x, channel_x], [y - 0.31, y + 0.31], color=color, lw=2.35)
    # Insulated gate and gate lead.
    line(ax, [x - 0.04, x - 0.04], [y - 0.32, y + 0.32], color=color, lw=2.0)
    line(ax, [gate_x - 0.34, gate_x], [y, y], color=color, lw=1.8)
    if kind == "p":
        ax.add_patch(Circle((gate_x + 0.08, y), 0.085, facecolor="white", edgecolor=color, lw=1.7, zorder=4))
        line(ax, [gate_x + 0.165, x - 0.04], [y, y], color=color, lw=1.8)
    else:
        line(ax, [gate_x, x - 0.04], [y, y], color=color, lw=1.8)
    # Body tie stub: explicitly shown and annotated by the surrounding rail.
    line(ax, [channel_x, channel_x + 0.28], [y, y], color=color, lw=1.4)
    # Device annotation.
    dx = 0.5 if label_side == "right" else -0.58
    ha = label_ha or ("left" if label_side == "right" else "right")
    lx, ly = label_xy or (x + dx, y + 0.20)
    ax.text(lx, ly, name, color=INK, fontsize=9, weight="bold", ha=ha, va="center")
    ax.text(lx, ly - 0.25, size, color=MUTED, fontsize=7.5, ha=ha, va="center")
    if note:
        ax.text(lx, ly - 0.50, note, color=MUTED, fontsize=7.1, ha=ha, va="center")
    return {
        "top": (channel_x, y + h),
        "bottom": (channel_x, y - h),
        "gate": (gate_x - 0.34, y),
        "body": (channel_x + 0.28, y),
    }


def resistor_h(ax, x0, x1, y, label):
    lead = 0.18
    line(ax, [x0, x0 + lead], [y, y], color=ORANGE)
    line(ax, [x1 - lead, x1], [y, y], color=ORANGE)
    xa, xb = x0 + lead, x1 - lead
    n = 7
    xs = [xa]
    ys = [y]
    for i in range(1, n + 1):
        xs.append(xa + (xb - xa) * i / (n + 1))
        ys.append(y + (0.12 if i % 2 else -0.12))
    xs.append(xb)
    ys.append(y)
    line(ax, xs, ys, color=ORANGE, lw=1.8)
    ax.text((x0 + x1) / 2, y + 0.28, label, color=ORANGE, fontsize=8, weight="bold", ha="center")


def capacitor_h(ax, x0, x1, y, label):
    mid = (x0 + x1) / 2
    gap = 0.11
    line(ax, [x0, mid - gap], [y, y], color=ORANGE)
    line(ax, [mid + gap, x1], [y, y], color=ORANGE)
    line(ax, [mid - gap, mid - gap], [y - 0.25, y + 0.25], color=ORANGE, lw=2.0)
    line(ax, [mid + gap, mid + gap], [y - 0.25, y + 0.25], color=ORANGE, lw=2.0)
    ax.text(mid, y + 0.39, label, color=ORANGE, fontsize=8, weight="bold", ha="center")


def current_sink(ax, x, y_top, y_bottom):
    yc = (y_top + y_bottom) / 2
    r = 0.30
    line(ax, [x, x], [y_top, yc + r], color=GREEN)
    line(ax, [x, x], [yc - r, y_bottom], color=GREEN)
    ax.add_patch(Circle((x, yc), r, facecolor="white", edgecolor=GREEN, lw=1.8, zorder=3))
    ax.add_patch(
        FancyArrowPatch(
            (x, yc + 0.15),
            (x, yc - 0.16),
            arrowstyle="-|>",
            mutation_scale=11,
            lw=1.4,
            color=GREEN,
            zorder=5,
        )
    )


def resistor_v(ax, x, y0, y1, label, *, color=ORANGE):
    lead = 0.15
    line(ax, [x, x], [y0, y0 - lead], color=color)
    line(ax, [x, x], [y1 + lead, y1], color=color)
    ya, yb = y0 - lead, y1 + lead
    n = 7
    xs = [x]
    ys = [ya]
    for i in range(1, n + 1):
        ys.append(ya + (yb - ya) * i / (n + 1))
        xs.append(x + (0.11 if i % 2 else -0.11))
    xs.append(x)
    ys.append(yb)
    line(ax, xs, ys, color=color, lw=1.5)
    ax.text(x + 0.22, (y0 + y1) / 2, label, color=color, fontsize=7.1, va="center")


def capacitor_v(ax, x, y0, y1, label, *, color=ORANGE):
    mid = (y0 + y1) / 2
    gap = 0.09
    line(ax, [x, x], [y0, mid + gap], color=color)
    line(ax, [x, x], [mid - gap, y1], color=color)
    line(ax, [x - 0.22, x + 0.22], [mid + gap, mid + gap], color=color, lw=1.8)
    line(ax, [x - 0.22, x + 0.22], [mid - gap, mid - gap], color=color, lw=1.8)
    ax.text(x + 0.27, mid, label, color=color, fontsize=7.1, va="center")


def add_core(ax):
    # Rails.
    line(ax, [4.75, 15.1], [8.55, 8.55], color=BLUE_DARK, lw=2.3)
    line(ax, [4.75, 15.1], [2.35, 2.35], color=INK, lw=2.3)
    net_label(ax, 4.90, 8.67, "VDD = 1.8 V", color=BLUE_DARK)
    net_label(ax, 4.90, 2.20, "VSS = 0 V", color=INK, va="top")

    # PMOS mirror-load composites (each is two explicit parallel units).
    m3 = mos(
        ax,
        6.20,
        7.15,
        "p",
        "M3A || M3B",
        "each 25 / 0.5 µm",
        note="diode-connected",
        label_xy=(4.95, 7.96),
        label_ha="left",
    )
    m4 = mos(
        ax,
        9.15,
        7.15,
        "p",
        "M4A || M4B",
        "each 25 / 0.5 µm",
        note="mirror output",
        label_xy=(8.45, 7.96),
        label_ha="left",
    )
    line(ax, [m3["top"][0], m3["top"][0]], [m3["top"][1], 8.55], color=BLUE_DARK)
    line(ax, [m4["top"][0], m4["top"][0]], [m4["top"][1], 8.55], color=BLUE_DARK)
    # NMOS input pair.
    m1 = mos(
        ax,
        6.20,
        4.70,
        "n",
        "M1",
        "16.83798 / 0.5 µm",
        note="VIN− side",
        label_xy=(5.18, 5.28),
        label_ha="left",
    )
    m2 = mos(
        ax,
        9.15,
        4.70,
        "n",
        "M2",
        "16.83798 / 0.5 µm",
        note="VIN+ side",
        label_xy=(9.62, 5.28),
        label_ha="left",
    )
    line(ax, [m3["bottom"][0], m1["top"][0]], [m3["bottom"][1], m1["top"][1]])
    line(ax, [m4["bottom"][0], m2["top"][0]], [m4["bottom"][1], m2["top"][1]])
    node(ax, m3["bottom"][0], 5.92)
    node(ax, m4["bottom"][0], 5.92)
    net_label(ax, m3["bottom"][0] + 0.12, 5.92, "NMIR", va="center")
    net_label(ax, m4["bottom"][0] + 0.12, 5.92, "VX", va="center")

    # M3 diode and M4 mirror gate connections.
    line(ax, [m3["gate"][0], 5.40, 5.40, m3["bottom"][0]], [m3["gate"][1], m3["gate"][1], 5.92, 5.92])
    line(ax, [m4["gate"][0], 7.40, 7.40, m3["bottom"][0]], [m4["gate"][1], m4["gate"][1], 5.92, 5.92])

    # External input pins.
    line(ax, [4.92, m1["gate"][0]], [m1["gate"][1], m1["gate"][1]], color=BLUE_DARK, lw=2.0)
    line(ax, [8.00, m2["gate"][0]], [m2["gate"][1], m2["gate"][1]], color=BLUE_DARK, lw=2.0)
    net_label(ax, 4.85, m1["gate"][1], "VIN−", color=BLUE_DARK, ha="right", va="center")
    net_label(ax, 7.93, m2["gate"][1], "VIN+", color=BLUE_DARK, ha="right", va="center")

    # Shared source and tail sink.
    tail_y = 3.74
    line(ax, [m1["bottom"][0], m1["bottom"][0]], [m1["bottom"][1], tail_y])
    line(ax, [m2["bottom"][0], m2["bottom"][0]], [m2["bottom"][1], tail_y])
    line(ax, [m1["bottom"][0], m2["bottom"][0]], [tail_y, tail_y])
    node(ax, 7.78, tail_y)
    net_label(ax, 7.90, tail_y, "TAIL", va="center")
    m5 = mos(
        ax,
        7.64,
        2.98,
        "n",
        "M5",
        "25.8754 / 0.8 µm",
        note="tail sink",
        label_xy=(8.18, 3.35),
        label_ha="left",
    )
    line(ax, [m5["top"][0], m5["top"][0]], [m5["top"][1], tail_y])
    line(ax, [m5["bottom"][0], m5["bottom"][0]], [m5["bottom"][1], 2.35])
    net_label(ax, m5["gate"][0] - 0.10, m5["gate"][1], "VBN", color=GREEN, ha="right", va="center")

    # Second stage.
    m7 = mos(
        ax,
        13.35,
        7.10,
        "p",
        "M7",
        "72.2005 / 0.8 µm",
        note="PMOS current source",
        label_xy=(13.83, 7.48),
        label_ha="left",
    )
    m6 = mos(
        ax,
        13.35,
        3.92,
        "n",
        "M6",
        "8.83907427 / 0.5 µm",
        note="common-source stage",
        label_xy=(13.83, 4.30),
        label_ha="left",
    )
    line(ax, [m7["top"][0], m7["top"][0]], [m7["top"][1], 8.55], color=BLUE_DARK)
    line(ax, [m6["bottom"][0], m6["bottom"][0]], [m6["bottom"][1], 2.35])
    line(ax, [m7["bottom"][0], m7["bottom"][0]], [m7["bottom"][1], 5.55])
    line(ax, [m6["top"][0], m6["top"][0]], [m6["top"][1], 5.55])
    node(ax, m7["bottom"][0], 5.55)
    line(ax, [m7["bottom"][0], 15.05], [5.55, 5.55], color=BLUE_DARK, lw=2.2)
    net_label(ax, 14.95, 5.68, "VOUT", color=BLUE_DARK, ha="right")
    net_label(ax, m7["gate"][0] - 0.08, m7["gate"][1], "VBP / IREF", color=GREEN, ha="right", va="center")

    # VX drives M6 gate.
    vx_x, vx_y = m4["bottom"][0], 5.92
    line(ax, [vx_x, 11.95, 11.95, m6["gate"][0]], [vx_y, vx_y, m6["gate"][1], m6["gate"][1]], color=TEAL)
    node(ax, vx_x, vx_y)

    # Series-Rz Miller path is part of the core, drawn distinctly.
    comp_y = 8.02
    comp_riser_x = 9.92
    line(ax, [vx_x, comp_riser_x], [vx_y, vx_y], color=ORANGE)
    line(ax, [comp_riser_x, comp_riser_x], [vx_y, comp_y], color=ORANGE)
    line(ax, [comp_riser_x, 10.05], [comp_y, comp_y], color=ORANGE)
    resistor_h(ax, 10.05, 11.20, comp_y, "RZ = 2 kΩ")
    capacitor_h(ax, 11.20, 12.35, comp_y, "CC = 3 pF")
    line(ax, [12.35, 14.10, 14.10, m7["bottom"][0]], [comp_y, comp_y, 5.55, 5.55], color=ORANGE)
    node(ax, vx_x, vx_y, color=ORANGE)
    node(ax, comp_riser_x, comp_y, color=ORANGE)
    node(ax, m7["bottom"][0], 5.55)
    net_label(ax, 9.42, 6.09, "VX → compensation", color=ORANGE, size=6.9)
    net_label(ax, 11.16, 7.72, "NCOMP", color=ORANGE, ha="center", va="top", size=7.2)
    ax.text(4.78, 1.74, "Body ties: all PMOS → VDD; all NMOS → VSS", color=MUTED, fontsize=7.2, weight="bold")


def add_bias(ax):
    line(ax, [0.72, 3.95], [8.55, 8.55], color=BLUE_DARK, lw=2.3)
    line(ax, [0.72, 3.95], [2.35, 2.35], color=INK, lw=2.3)
    net_label(ax, 0.83, 8.67, "VDD", color=BLUE_DARK)
    net_label(ax, 0.83, 2.20, "VSS", color=INK, va="top")
    m8 = mos(
        ax,
        1.45,
        6.90,
        "p",
        "M8",
        "7.22005 / 0.8 µm",
        note="diode VBP",
        label_xy=(0.68, 7.88),
        label_ha="left",
    )
    m9 = mos(
        ax,
        3.00,
        6.90,
        "p",
        "M9",
        "7.22005 / 0.8 µm",
        note="VBN branch",
        label_xy=(2.38, 7.88),
        label_ha="left",
    )
    m10 = mos(
        ax,
        3.00,
        3.95,
        "n",
        "M10",
        "8.08605 / 0.8 µm",
        note="diode VBN",
        label_xy=(2.35, 4.90),
        label_ha="left",
    )
    for dev in (m8, m9):
        line(ax, [dev["top"][0], dev["top"][0]], [dev["top"][1], 8.55], color=BLUE_DARK)
    line(ax, [m10["bottom"][0], m10["bottom"][0]], [m10["bottom"][1], 2.35])
    # M8 diode connection and IREF current sink.
    vbp_y = m8["bottom"][1]
    line(ax, [m8["bottom"][0], 0.82, 0.82, m8["gate"][0]], [vbp_y, vbp_y, m8["gate"][1], m8["gate"][1]], color=GREEN)
    node(ax, m8["bottom"][0], vbp_y, color=GREEN)
    net_label(ax, 0.78, vbp_y - 0.10, "VBP = IREF", color=GREEN, va="top")
    current_sink(ax, 1.60, vbp_y, 2.35)
    line(ax, [m8["bottom"][0], 1.60], [vbp_y, vbp_y], color=GREEN)
    ax.text(1.72, 4.45, "IREF\n10 µA", color=GREEN, fontsize=8, weight="bold", va="center")
    # M9 gate mirrors VBP; M9/M10 establish VBN.
    line(ax, [m9["gate"][0], 2.18, 2.18, m8["bottom"][0]], [m9["gate"][1], m9["gate"][1], vbp_y, vbp_y], color=GREEN)
    line(ax, [m9["bottom"][0], m10["top"][0]], [m9["bottom"][1], m10["top"][1]], color=GREEN)
    line(ax, [m10["gate"][0], 2.38, 2.38, m10["top"][0]], [m10["gate"][1], m10["gate"][1], m10["top"][1], m10["top"][1]], color=GREEN)
    node(ax, m10["top"][0], 5.43, color=GREEN)
    net_label(ax, m10["top"][0] + 0.12, 5.43, "VBN", color=GREEN, va="center")
    # Bias destinations outside panel.
    ax.add_patch(FancyArrowPatch((3.82, vbp_y), (4.38, vbp_y), arrowstyle="-|>", mutation_scale=12, color=GREEN, lw=1.5))
    ax.add_patch(FancyArrowPatch((3.82, 5.43), (4.38, 5.43), arrowstyle="-|>", mutation_scale=12, color=GREEN, lw=1.5))
    ax.text(3.78, vbp_y + 0.18, "to M7", color=GREEN, fontsize=7.1, ha="right")
    ax.text(3.78, 5.62, "to M5", color=GREEN, fontsize=7.1, ha="right")
    ax.text(0.70, 1.74, "Body ties: PMOS → VDD; NMOS → VSS", color=MUTED, fontsize=6.8, weight="bold")


def add_testbench(ax):
    # Unity-gain follower mini-diagram.
    ax.text(15.75, 8.48, "EXTERNAL VERIFICATION BENCH", color=ORANGE, fontsize=9.3, weight="bold", va="top")
    ax.text(15.75, 8.10, "Nominal: TT, 27 °C; CL = 5 pF, RL = 100 kΩ to VSS", color=MUTED, fontsize=7.2, va="top")
    tri = Polygon([[17.05, 6.34], [17.05, 7.48], [18.25, 6.91]], closed=True, facecolor="white", edgecolor=ORANGE, lw=1.8)
    ax.add_patch(tri)
    ax.text(17.18, 7.18, "+", color=ORANGE, fontsize=11, weight="bold")
    ax.text(17.18, 6.54, "−", color=ORANGE, fontsize=11, weight="bold")
    line(ax, [15.82, 17.05], [7.20, 7.20], color=ORANGE)
    ax.text(15.82, 7.39, "VIN+", color=ORANGE, fontsize=7.4, weight="bold")
    ax.text(15.82, 7.03, "0.8 ↔ 1.2 V", color=MUTED, fontsize=6.8)
    line(ax, [18.25, 19.67], [6.91, 6.91], color=ORANGE)
    node(ax, 18.70, 6.91, color=ORANGE)
    net_label(ax, 19.63, 7.04, "VOUT", color=ORANGE, ha="right")
    # Direct transient feedback clearly outside the core.
    line(ax, [18.70, 18.70, 16.62, 16.62, 17.05], [6.91, 6.05, 6.05, 6.56, 6.56], color=ORANGE)
    ax.text(16.67, 5.84, "direct feedback (transient)", color=MUTED, fontsize=6.7)
    # Parallel load.
    line(ax, [19.15, 19.15], [6.91, 6.48], color=ORANGE)
    resistor_v(ax, 18.88, 6.48, 5.55, "100 kΩ", color=ORANGE)
    capacitor_v(ax, 19.43, 6.48, 5.55, "5 pF", color=ORANGE)
    line(ax, [18.88, 19.43], [6.48, 6.48], color=ORANGE)
    line(ax, [18.88, 19.43], [5.55, 5.55], color=ORANGE)
    line(ax, [19.15, 19.15], [5.55, 5.25], color=ORANGE)
    ax.text(19.15, 5.08, "VSS", color=INK, fontsize=7.2, weight="bold", ha="center")

    # Loop-break inset, separate from the core and from direct transient loop.
    line(ax, [15.75, 19.82], [4.75, 4.75], color="#e6c997", lw=1.0)
    ax.text(15.75, 4.52, "Loop-gain bench only", color=ORANGE, fontsize=8.2, weight="bold", va="top")
    ax.text(15.75, 4.15, "DC feedback:", color=MUTED, fontsize=7.1, weight="bold", va="top")
    ax.text(17.20, 4.15, "LBREAK = 1 GH (DC short / AC open)", color=INK, fontsize=7.0, va="top")
    ax.text(15.75, 3.78, "AC injection:", color=MUTED, fontsize=7.1, weight="bold", va="top")
    ax.text(17.20, 3.78, "CBREAK = 1 GF from 1-V AC source", color=INK, fontsize=7.0, va="top")
    ax.text(15.75, 3.36, "Return ratio: T = −V(VOUT) / V(VIN−)", color=INK, fontsize=7.2, va="top")
    ax.text(15.75, 2.92, "LBREAK and CBREAK are analysis elements—", color=RED, fontsize=7.1, weight="bold", va="top")
    ax.text(15.75, 2.61, "they are not part of the OTA core.", color=RED, fontsize=7.1, weight="bold", va="top")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "axes.linewidth": 0.0,
        }
    )
    fig, ax = plt.subplots(figsize=(20, 11.2), facecolor="white")
    ax.set_xlim(0, 20.6)
    ax.set_ylim(0.65, 10.75)
    ax.axis("off")

    # Header.
    ax.text(0.55, 10.45, "SKY130A 1.8-V Two-Stage Miller-Compensated CMOS OTA", color=INK, fontsize=21, weight="bold", va="top")
    ax.text(
        0.57,
        10.03,
        "Frozen Day 3 design • single 10-µA reference • schematic-level simulation • device dimensions are W/L",
        color=MUTED,
        fontsize=10.3,
        va="top",
    )

    # Panel backgrounds and boundaries.
    panels = [
        (0.45, 1.55, 3.75, 7.50, BIAS_BG, GREEN, "BIAS GENERATION"),
        (4.50, 1.55, 10.75, 7.50, CORE_BG, BLUE, "OTA CORE"),
        (15.52, 1.55, 4.60, 7.50, TB_BG, ORANGE, "TESTBENCH (EXTERNAL)"),
    ]
    for x, y, w, h, face, edge, label in panels:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", facecolor=face, edgecolor=edge, lw=1.35, zorder=0))
        ax.text(x + 0.18, y + h - 0.18, label, color=edge, fontsize=8, weight="bold", va="top")

    add_bias(ax)
    add_core(ax)
    add_testbench(ax)

    # Footer notes distinguish evidence from claims.
    ax.text(
        0.55,
        1.18,
        "Connectivity source: schematics/two_stage_ota.sch and netlists/ota/two_stage_ota_core.spice",
        color=INK,
        fontsize=8.4,
        weight="bold",
        va="center",
    )
    ax.text(
        0.55,
        0.86,
        "No layout, extracted parasitics, silicon measurement, fabrication, or tapeout is represented by this drawing.",
        color=RED,
        fontsize=8.2,
        va="center",
    )
    ax.text(20.05, 0.86, "SKY130A • TT nominal annotations", color=MUTED, fontsize=7.5, ha="right", va="center")

    svg = OUT / "final_two_stage_ota_schematic.svg"
    png = OUT / "final_two_stage_ota_schematic.png"
    fig.savefig(svg, bbox_inches="tight", pad_inches=0.18)
    fig.savefig(png, dpi=220, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    # Matplotlib wraps SVG path data with trailing spaces. Normalize the text
    # so repository whitespace checks remain deterministic after regeneration.
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )
    print(svg)
    print(png)


if __name__ == "__main__":
    main()
