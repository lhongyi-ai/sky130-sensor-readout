#!/usr/bin/env python3
"""Build the six-page portfolio report from checked CSV and plot artifacts."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PLOTS = RESULTS / "plots"
OUTPUT = ROOT / "docs" / "sky130_two_stage_ota_report.pdf"

NAVY = colors.HexColor("#0B1F33")
BLUE = colors.HexColor("#176B87")
TEAL = colors.HexColor("#159A9C")
GREEN = colors.HexColor("#18794E")
PALE_GREEN = colors.HexColor("#E8F5EE")
RED = colors.HexColor("#B42318")
PALE_RED = colors.HexColor("#FFF0EE")
AMBER = colors.HexColor("#A15C00")
PALE_AMBER = colors.HexColor("#FFF6E5")
INK = colors.HexColor("#17212B")
MUTED = colors.HexColor("#5D6B78")
LINE = colors.HexColor("#D9E1E8")
PALE_BLUE = colors.HexColor("#EAF4F8")
WHITE = colors.white


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def esc(value: object) -> str:
    return html.escape(str(value))


def fnum(value: str | float, digits: int = 2) -> str:
    return f"{float(value):.{digits}f}"


def image(path: Path, width: float, max_height: float) -> Image:
    if not path.exists():
        raise FileNotFoundError(path)
    item = Image(str(path))
    scale = min(width / item.imageWidth, max_height / item.imageHeight)
    item.drawWidth = item.imageWidth * scale
    item.drawHeight = item.imageHeight * scale
    return item


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=27,
        leading=31,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=7,
    )
)
styles.add(
    ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12.5,
        leading=17,
        textColor=BLUE,
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=NAVY,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="Subhead",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=BLUE,
        spaceBefore=3,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.7,
        leading=12.0,
        textColor=INK,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyTiny",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.3,
        leading=9.3,
        textColor=INK,
    )
)
styles.add(
    ParagraphStyle(
        name="Caption",
        parent=styles["BodyText"],
        fontName="Helvetica-Oblique",
        fontSize=7.2,
        leading=9,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Eyebrow",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=TEAL,
        tracking=0.8,
        spaceAfter=9,
    )
)
styles.add(
    ParagraphStyle(
        name="CardValue",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=17,
        textColor=NAVY,
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        name="CardLabel",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
)


def p(text: str, style: str = "BodySmall") -> Paragraph:
    return Paragraph(text, styles[style])


def cell(text: object, bold: bool = False, color: colors.Color = INK) -> Paragraph:
    face = "Helvetica-Bold" if bold else "Helvetica"
    return Paragraph(
        esc(text),
        ParagraphStyle(
            name=f"cell-{face}-{color}",
            fontName=face,
            fontSize=7.2,
            leading=9.0,
            textColor=color,
        ),
    )


def styled_table(
    data: list[list[object]],
    widths: list[float],
    header: bool = True,
    font_size: float = 7.2,
    paddings: tuple[float, float] = (3.5, 3.5),
) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands: list[tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), paddings[0]),
        ("RIGHTPADDING", (0, 0), (-1, -1), paddings[0]),
        ("TOPPADDING", (0, 0), (-1, -1), paddings[1]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), paddings[1]),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, colors.HexColor("#F7F9FB")]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def outcome_table(rows: list[list[object]], widths: list[float], font_size: float = 7.2) -> Table:
    table = styled_table(rows, widths, font_size=font_size)
    commands: list[tuple] = []
    for index, row in enumerate(rows[1:], start=1):
        status = str(row[-1])
        if "PASS" in status:
            commands.extend(
                [
                    ("BACKGROUND", (-1, index), (-1, index), PALE_GREEN),
                    ("TEXTCOLOR", (-1, index), (-1, index), GREEN),
                    ("FONTNAME", (-1, index), (-1, index), "Helvetica-Bold"),
                ]
            )
        elif "FAIL" in status:
            commands.extend(
                [
                    ("BACKGROUND", (-1, index), (-1, index), PALE_RED),
                    ("TEXTCOLOR", (-1, index), (-1, index), RED),
                    ("FONTNAME", (-1, index), (-1, index), "Helvetica-Bold"),
                ]
            )
    table.setStyle(TableStyle(commands))
    return table


def callout(title: str, body: str, background: colors.Color, accent: colors.Color) -> Table:
    content = p(f"<b><font color='{accent.hexval()}'>{esc(title)}</font></b><br/>{body}", "BodySmall")
    table = Table([[content]], colWidths=[181 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.8, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def kpi_cards(cards: list[tuple[str, str]]) -> Table:
    cells: list[list[object]] = []
    row: list[object] = []
    for value, label in cards:
        row.append([p(esc(value), "CardValue"), p(esc(label), "CardLabel")])
        if len(row) == 3:
            cells.append(row)
            row = []
    if row:
        while len(row) < 3:
            row.append("")
        cells.append(row)
    table = Table(cells, colWidths=[60.3 * mm] * 3, rowHeights=[18 * mm] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("GRID", (0, 0), (-1, -1), 1, WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.45)
    canvas.line(doc.leftMargin, 14 * mm, width - doc.rightMargin, 14 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.8)
    canvas.drawString(doc.leftMargin, 9.5 * mm, "SKY130 two-stage OTA | schematic-level simulation only")
    page_text = f"{doc.page} / 6"
    canvas.drawString(width - doc.rightMargin - stringWidth(page_text, "Helvetica", 6.8), 9.5 * mm, page_text)
    canvas.restoreState()


def build_story() -> list[object]:
    summary_rows = read_rows(RESULTS / "summary.csv")
    summary = {row["metric"]: row for row in summary_rows}
    pvt = read_rows(RESULTS / "pvt_summary.csv")
    load = read_rows(RESULTS / "day4_load_stability.csv")
    day3 = {row["metric"]: row for row in read_rows(RESULTS / "day3_nominal_summary.csv")}
    comp = read_rows(RESULTS / "day3_compensation_before_after.csv")
    day5 = {row["tag"]: row for row in read_rows(ROOT / "experiments" / "day5" / "recon_summary.csv")}
    decision = read_rows(ROOT / "experiments" / "day5" / "decision_summary.csv")[0]

    manifest_hashes = {row["manifest_sha256"] for row in summary_rows if row.get("manifest_sha256")}
    if len(manifest_hashes) != 1:
        raise ValueError("results/summary.csv must contain exactly one Day 4 manifest hash")
    manifest_hash = manifest_hashes.pop()
    if len(pvt) != 13 or len(load) != 3:
        raise ValueError("Expected exactly 13 PVT points and three nominal load points")

    story: list[object] = []

    # Page 1 — outcome first.
    story.extend(
        [
            Spacer(1, 14 * mm),
            p("ANALOG IC DESIGN PORTFOLIO | SKY130A | 2026", "Eyebrow"),
            p("Specification-Driven Two-Stage CMOS OTA", "ReportTitle"),
            p(
                "A reproducible 1.8 V Miller-compensated design, from device characterization "
                "through 13-point PVT verification and explicit failure reporting.",
                "ReportSubtitle",
            ),
            HRFlowable(width="100%", thickness=2.2, color=TEAL, spaceAfter=12),
            p(
                "The final M1-M10 OTA uses a single external 10 uA reference, a 3 pF Miller "
                "capacitor, and a 2 kohm series nulling resistor. All six frozen core metrics pass "
                "their hard and stretch targets at every required PVT point. The full nominal "
                "characterization also exposes two unresolved requirements: PSRR and the 1.3 V "
                "high end of ICMR.",
            ),
            Spacer(1, 2 * mm),
            kpi_cards(
                [
                    (fnum(summary["Open-loop DC gain"]["worst_pvt_result"]), "worst A0 (dB)"),
                    (fnum(summary["Unity-gain bandwidth"]["worst_pvt_result"]), "worst UGB (MHz)"),
                    (fnum(summary["Phase margin"]["worst_pvt_result"]), "worst PM (deg)"),
                    (fnum(summary["Quiescent power"]["worst_pvt_result"]), "max power (uW)"),
                    (fnum(summary["Positive slew rate"]["worst_pvt_result"]), "worst SR+ (V/us)"),
                    (fnum(summary["Negative slew rate"]["worst_pvt_result"]), "worst SR- (V/us)"),
                ]
            ),
            Spacer(1, 4 * mm),
            p("Qualification snapshot", "Subhead"),
            outcome_table(
                [
                    ["Scope", "Result", "Frozen requirement", "Status"],
                    ["13-point core PVT", "A0 / UGB / PM / power / SR+ / SR-", "all 13 points", "PASS"],
                    ["Nominal settling", f'{fnum(summary["1% settling time"]["nominal_result"], 4)} us', "<= 1.5 us", "PASS"],
                    ["Nominal CMRR @ 1 kHz", f'{fnum(summary["CMRR at 1 kHz"]["nominal_result"])} dB', ">= 55 dB", "PASS"],
                    ["Nominal output swing", "0.18-1.63 V", "contains 0.3-1.5 V", "PASS"],
                    ["Nominal PSRR+ / PSRR-", "36.33 / 36.25 dB", ">= 45 dB each", "FAIL"],
                    ["Nominal ICMR", "0.76-1.22 V", "contains 0.8-1.3 V", "FAIL"],
                ],
                [37 * mm, 58 * mm, 51 * mm, 35 * mm],
            ),
            Spacer(1, 4 * mm),
            callout(
                "Truth boundary",
                "These are transistor-level <b>schematic simulations</b>, not fabricated, measured, "
                "post-layout, or Monte Carlo results. The external IREF is ideal. Failed requirements "
                "remain visible and are not promoted to passes.",
                PALE_RED,
                RED,
            ),
            Spacer(1, 4 * mm),
            p(
                f"Evidence bundle: 171 completed ngspice decks; Day 4 manifest "
                f"<font face='Courier'>{manifest_hash[:16]}...</font>",
                "BodyTiny",
            ),
            PageBreak(),
        ]
    )

    # Page 2 — topology and sizing.
    story.extend(
        [
            p("1. Architecture and sizing", "SectionTitle"),
            p(
                "An NMOS differential pair and PMOS mirror load form the first stage. M6/M7 form "
                "the common-source output stage. M8-M10 translate one external reference current "
                "into the PMOS and NMOS bias voltages. The compensation branch is strictly VX -> "
                "RZ -> CC -> VOUT; loop-break and load elements live only in testbenches.",
            ),
            image(PLOTS / "final_two_stage_ota_schematic.png", 181 * mm, 103 * mm),
            p("Figure 1. Verified Xschem transistor-level OTA core and pin interface.", "Caption"),
            p("Final device geometry", "Subhead"),
            styled_table(
                [
                    ["Devices", "Function", "Geometry (W/L, um)", "Nominal role"],
                    ["M1 / M2", "NMOS input pair", "16.83798 / 0.5 each", "gm and UGB"],
                    ["M3 / M4", "PMOS mirror load", "2 x 25 / 0.5 per side", "diff-to-single-ended"],
                    ["M5", "NMOS tail source", "25.8754 / 0.8", "38 uA tail bias"],
                    ["M6 / M7", "second stage", "8.83907 / 0.5; 72.2005 / 0.8", "gain and output drive"],
                    ["M8 / M9 / M10", "bias tree", "7.22005 / 0.8; 7.22005 / 0.8; 8.08605 / 0.8", "10 uA IREF translation"],
                    ["CC / RZ", "Miller network", "3 pF / 2 kohm", "pole split and zero control"],
                ],
                [24 * mm, 41 * mm, 61 * mm, 55 * mm],
            ),
            Spacer(1, 3 * mm),
            callout(
                "Sizing method",
                "Device lookup tables supplied gm/ID, intrinsic-gain, and VDSAT guidance. Block-level "
                "iterations then checked current symmetry, gain, headroom, and area/bandwidth tradeoffs "
                "before the complete OTA was tuned. At nominal, all M1-M10 saturation margins are "
                "positive; the minimum is 0.116 V at M5.",
                PALE_BLUE,
                BLUE,
            ),
            PageBreak(),
        ]
    )

    # Page 3 — nominal dynamics and compensation.
    nominal_rows = [
        ["Metric", "Nominal", "Hard / stretch", "Status"],
        ["A0", "67.68 dB", ">= 50 / 60 dB", "PASS"],
        ["UGB", "16.75 MHz", ">= 5 / 10 MHz", "PASS"],
        ["Phase margin", "69.08 deg", ">= 55 / 65 deg", "PASS"],
        ["Power", "270.54 uW", "<= 600 / 400 uW", "PASS"],
        ["SR+ / SR-", "8.20 / 11.52 V/us", ">= 2 / 4 V/us", "PASS"],
        ["Worst 1% settling", "0.07475 us", "<= 1.5 / 1.0 us", "PASS"],
    ]
    story.extend(
        [
            p("2. Nominal compensation and transient response", "SectionTitle"),
            p(
                "Loop gain uses a DC-closed/AC-open break: a 1 GH inductor preserves follower bias "
                "while a 1 GF capacitor injects the AC perturbation. The signed return ratio is "
                "T=-VOUT/VINN; UGB is the first downward 0 dB crossing and PM is evaluated there.",
            ),
            Table(
                [
                    [image(PLOTS / "day3_loop_gain_compensation.png", 87.5 * mm, 72 * mm), image(PLOTS / "day3_unity_follower_transient.png", 87.5 * mm, 72 * mm)],
                    [p("Figure 2. Compensation sweep and selected loop response.", "Caption"), p("Figure 3. 0.8-1.2-0.8 V unity-follower transient.", "Caption")],
                ],
                colWidths=[90.5 * mm, 90.5 * mm],
                hAlign="LEFT",
                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 1.5), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5)]),
            ),
            p("Selected nominal result", "Subhead"),
            outcome_table(nominal_rows, [43 * mm, 43 * mm, 58 * mm, 37 * mm]),
            Spacer(1, 4 * mm),
            p("Documented optimization: nulling resistor", "Subhead"),
            outcome_table(
                [
                    ["Configuration", "A0", "UGB", "PM", "Disposition"],
                    ["CC=3 pF, RZ~0", "67.67 dB", "17.26 MHz", "33.22 deg", "FAIL"],
                    ["CC=3 pF, RZ=1 kohm", "67.67 dB", "16.36 MHz", "52.29 deg", "FAIL"],
                    ["CC=3 pF, RZ=2 kohm", "67.67 dB", "16.75 MHz", "69.08 deg", "PASS / selected"],
                ],
                [50 * mm, 31 * mm, 34 * mm, 29 * mm, 37 * mm],
            ),
            Spacer(1, 3 * mm),
            p(
                "The selected 2 kohm resistor raises nominal PM by 35.86 degrees relative to the "
                "capacitor-only case while changing UGB by about -3%. Slew rate is a least-squares "
                "fit over directed monotonic 20-80% segments; settling starts at the interpolated "
                "input 50% crossing and requires the output to remain inside a 4 mV band.",
            ),
            PageBreak(),
        ]
    )

    # Page 4 — PVT and load robustness.
    worst_rows = [
        ["Metric", "Nominal", "Worst PVT", "Condition", "Hard", "Status"],
    ]
    for label, key, hard in [
        ("A0 (dB)", "Open-loop DC gain", ">=50"),
        ("UGB (MHz)", "Unity-gain bandwidth", ">=5"),
        ("PM (deg)", "Phase margin", ">=55"),
        ("Power (uW)", "Quiescent power", "<=600"),
        ("SR+ (V/us)", "Positive slew rate", ">=2"),
        ("SR- (V/us)", "Negative slew rate", ">=2"),
    ]:
        row = summary[key]
        worst_rows.append([label, fnum(row["nominal_result"]), fnum(row["worst_pvt_result"]), row["worst_condition"], hard, row["status"]])
    story.extend(
        [
            p("3. PVT and load robustness", "SectionTitle"),
            p(
                "The fixed matrix contains TT/FF/SS/FS/SF at 1.8 V and 27 C plus the TT combinations "
                "of 1.62/1.80/1.98 V and -20/27/85 C, with the duplicated nominal point counted once.",
            ),
            Table(
                [
                    [image(PLOTS / "day4_pvt_summary.png", 105 * mm, 82 * mm), outcome_table(worst_rows, [18 * mm, 10 * mm, 13 * mm, 10 * mm, 9 * mm, 13 * mm], font_size=5.6)],
                ],
                colWidths=[108 * mm, 73 * mm],
                hAlign="LEFT",
                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1)]),
            ),
            p("Figure 4. All six core metrics pass at every required PVT point.", "Caption"),
            Spacer(1, 2 * mm),
            p("Nominal load sweep", "Subhead"),
            Table(
                [
                    [
                        image(PLOTS / "day4_load_stability.png", 112 * mm, 70 * mm),
                        outcome_table(
                            [
                                ["CL", "UGB", "PM", "Status"],
                                *[
                                    [
                                        f'{fnum(row["CL_pF"], 0)} pF',
                                        f'{fnum(row["ugb_MHz"])} MHz',
                                        f'{fnum(row["pm_deg"])} deg',
                                        row["status"],
                                    ]
                                    for row in load
                                ],
                            ],
                            [10 * mm, 19 * mm, 18 * mm, 20 * mm],
                            font_size=6.2,
                        ),
                    ]
                ],
                colWidths=[114 * mm, 67 * mm],
                hAlign="LEFT",
                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1)]),
            ),
            p(
                "Figure 5. CL=1/2/5 pF with RL=100 kohm. All three PM values exceed 55 degrees "
                "and the corresponding unity-follower transients show no sustained or growing oscillation.",
                "Caption",
            ),
            callout(
                "Integrity gates",
                "Every required log must finish once without fatal diagnostics; raw grids must have "
                "their declared point counts and finite values; loop crossings cannot be ambiguous or "
                "land on a sweep boundary. The Day 3 and Day 4 nominal metrics also correlate within "
                "their explicit tolerances.",
                PALE_GREEN,
                GREEN,
            ),
            PageBreak(),
        ]
    )

    # Page 5 — complete nominal characterization.
    figure_grid = Table(
        [
            [image(PLOTS / "day4_icmr.png", 87.5 * mm, 61 * mm), image(PLOTS / "day4_output_swing.png", 87.5 * mm, 61 * mm)],
            [p("Figure 6. ICMR criteria and limiting interval.", "Caption"), p("Figure 7. Forward/reverse output-swing audit.", "Caption")],
            [image(PLOTS / "day4_cmrr_psrr.png", 87.5 * mm, 55 * mm), image(PLOTS / "day4_noise.png", 87.5 * mm, 55 * mm)],
            [p("Figure 8. CMRR and both PSRR responses.", "Caption"), p("Figure 9. Input-referred noise density.", "Caption")],
        ],
        colWidths=[90.5 * mm, 90.5 * mm],
        hAlign="LEFT",
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 1.5), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5)]),
    )
    story.extend(
        [
            p("4. Complete nominal characterization", "SectionTitle"),
            figure_grid,
            outcome_table(
                [
                    ["Metric", "Measured result", "Requirement", "Status"],
                    ["ICMR", "0.76-1.22 V", "contains 0.8-1.3 V", "FAIL"],
                    ["Output swing", "0.18-1.63 V", "contains 0.3-1.5 V", "PASS"],
                    ["CMRR @ 1 kHz", "71.32 dB", ">=55 dB", "PASS"],
                    ["PSRR+ / PSRR- @ 1 kHz", "36.33 / 36.25 dB", ">=45 dB each", "FAIL"],
                    ["Noise @ 1 kHz", "401.17 nV/sqrt(Hz)", "report", "REPORTED"],
                    ["Integrated noise, 10 Hz-1 MHz", "52.30 uV RMS", "report", "REPORTED"],
                ],
                [47 * mm, 51 * mm, 52 * mm, 31 * mm],
            ),
            Spacer(1, 3 * mm),
            p(
                "ICMR is the largest continuous 10 mV-grid interval around 0.9 V satisfying gain "
                "flatness, M1-M10 saturation, and output rail guard criteria. Output swing is measured "
                "separately with equal 10 Mohm input/feedback resistors, <=10 mV tracking error, "
                "M6/M7 saturation, and agreement between forward and reverse sweeps. Noise is report-only; "
                "24 model conductance-reset warnings are retained in the audit trail.",
            ),
            PageBreak(),
        ]
    )

    # Page 6 — decision, limitations, and reproduction.
    base = day5["baseline"]
    candidate = day5["first_stage_l2"]
    story.extend(
        [
            p("5. Design decision, limits, and reproduction", "SectionTitle"),
            p("Day 5 bounded optimization screen", "Subhead"),
            p(
                "A nominal-only experiment doubled M1-M4 channel length while preserving W/L. It "
                "improved supply rejection, but reduced stability margin, worsened the 1.3 V ICMR "
                "checkpoint, and greatly increased device area. It was therefore rejected; the frozen "
                "Day 4 geometry remains the reported schematic-level baseline.",
            ),
            outcome_table(
                [
                    ["Metric", "Frozen baseline", "M1-M4 Lx2", "Change / consequence"],
                    ["A0", f'{fnum(base["a0_db"])} dB', f'{fnum(candidate["a0_db"])} dB', "+6.70 dB"],
                    ["Phase margin", f'{fnum(base["pm_deg"])} deg', f'{fnum(candidate["pm_deg"])} deg', "-7.56 deg; stretch miss"],
                    ["PSRR+ / PSRR-", f'{fnum(base["psrr_plus_1k_db"])} / {fnum(base["psrr_minus_1k_db"])} dB', f'{fnum(candidate["psrr_plus_1k_db"])} / {fnum(candidate["psrr_minus_1k_db"])} dB', "large nominal improvement"],
                    ["1.3 V ICMR gain delta", f'{fnum(base["icmr_1p3_gain_delta_db"])} dB', f'{fnum(candidate["icmr_1p3_gain_delta_db"])} dB', f'worse by {abs(float(candidate["delta_icmr_1p3_gain_db"])):.2f} dB'],
                    ["Gate-area proxy", "1.00x", f'{fnum(candidate["total_gate_area_factor_vs_baseline"], 2)}x', "M1-M4 area is 4x"],
                    ["Decision", "KEEP", "REJECT", decision["day5_candidate_disposition"]],
                ],
                [42 * mm, 37 * mm, 37 * mm, 65 * mm],
            ),
            Spacer(1, 4 * mm),
            Table(
                [
                    [
                        [
                            p("Reproduce", "Subhead"),
                            p(
                                "1. Start Colima/Docker.<br/>"
                                "2. Use the pinned IIC-OSIC image and SKY130A revision.<br/>"
                                "3. Run <font face='Courier'>./scripts/run_all.sh</font>.<br/>"
                                "4. Inspect <font face='Courier'>results/summary.csv</font>, the PVT table, plots, and manifest-stamped raw TSV files.<br/>"
                                "5. Open <font face='Courier'>schematics/two_stage_ota.sch</font> in Xschem for the editable schematic.",
                                "BodyTiny",
                            ),
                        ],
                        [
                            p("Known limitations", "Subhead"),
                            p(
                                "- PSRR+ and PSRR- miss the 45 dB hard limit.<br/>"
                                "- ICMR stops at 1.22 V, below the required 1.3 V.<br/>"
                                "- IREF is ideal; reference-generator variation is absent.<br/>"
                                "- No mismatch, Monte Carlo, layout, extraction, package, board, or silicon data.<br/>"
                                "- Non-core metrics were characterized only at nominal.",
                                "BodyTiny",
                            ),
                        ],
                    ]
                ],
                colWidths=[88.5 * mm, 88.5 * mm],
                hAlign="LEFT",
                style=TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 0), (0, 0), PALE_BLUE),
                        ("BACKGROUND", (1, 0), (1, 0), PALE_AMBER),
                        ("BOX", (0, 0), (0, 0), 0.7, BLUE),
                        ("BOX", (1, 0), (1, 0), 0.7, AMBER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
            Spacer(1, 5 * mm),
            callout(
                "Conclusion",
                "This project demonstrates a complete and auditable analog-design workflow: "
                "requirements were frozen before tuning, calculations were tied to device data, "
                "loop stability was measured with an explicit return-ratio bench, PVT coverage was "
                "automated, and unfavorable results were preserved. The design is a credible "
                "schematic-level portfolio artifact precisely because its pass boundary and remaining "
                "engineering work are explicit.",
                PALE_GREEN,
                GREEN,
            ),
            Spacer(1, 5 * mm),
            p(
                "Primary evidence: README.md | docs/specification.md | results/summary.csv | "
                "results/pvt_summary.csv | experiments/day5/assessment.md",
                "BodyTiny",
            ),
        ]
    )

    return story


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=14.5 * mm,
        leftMargin=14.5 * mm,
        topMargin=15 * mm,
        bottomMargin=19 * mm,
        title="Specification-Driven Two-Stage CMOS OTA",
        author="SKY130 Two-Stage OTA Project",
        subject="Schematic-level analog IC design and verification report",
    )
    document.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    pages = len(PdfReader(str(OUTPUT)).pages)
    if pages != 6:
        raise RuntimeError(f"Expected exactly 6 report pages, generated {pages}")
    print(f"REPORT_OK path={OUTPUT} pages={pages}")


if __name__ == "__main__":
    main()
