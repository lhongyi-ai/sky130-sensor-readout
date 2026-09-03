#!/usr/bin/env python3
"""Render portable SPICE templates against the installed SKY130A model deck."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


MODEL_CANDIDATES = (
    "/foss/pdks/sky130A/libs.tech/ngspice/sky130.lib.spice",
    "/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice",
    "/usr/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice",
    "/usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice",
)


def find_model_deck() -> Path:
    configured = os.environ.get("SKY130_MODEL_DECK")
    candidates = ([configured] if configured else []) + list(MODEL_CANDIDATES)
    pdk_root = os.environ.get("PDK_ROOT")
    if pdk_root:
        candidates.extend(
            [
                f"{pdk_root}/sky130A/libs.tech/ngspice/sky130.lib.spice",
                f"{pdk_root}/sky130A/libs.tech/combined/sky130.lib.spice",
            ]
        )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    searched = "\n  - ".join(str(item) for item in candidates if item)
    raise FileNotFoundError(f"SKY130A model deck not found. Searched:\n  - {searched}")


def length_tag(length_um: float) -> str:
    return f"{length_um:g}".replace(".", "p")


def render_template(
    template: Path,
    output_dir: Path,
    model_deck: Path,
    corner: str,
    lengths_um: list[float],
) -> list[Path]:
    source = template.read_text(encoding="utf-8")
    base = template.name.removesuffix(".spice.in")
    variants: list[tuple[str, str]]
    if "@@LENGTH_UM@@" in source or "@@LENGTH_TAG@@" in source:
        variants = [(f"_l{length_tag(value)}", f"{value:g}") for value in lengths_um]
    else:
        variants = [("", "")]

    written: list[Path] = []
    for suffix, length in variants:
        rendered = source.replace("@@MODEL_DECK@@", str(model_deck)).replace(
            "@@CORNER@@", corner
        )
        if length:
            rendered = rendered.replace("@@LENGTH_UM@@", length).replace(
                "@@LENGTH_TAG@@", length_tag(float(length))
            )
        unresolved = [token for token in ("@@MODEL_DECK@@", "@@CORNER@@", "@@LENGTH_UM@@", "@@LENGTH_TAG@@") if token in rendered]
        if unresolved:
            raise ValueError(f"Unresolved placeholders in {template}: {unresolved}")
        output = output_dir / f"{base}{suffix}.spice"
        output.write_text(rendered, encoding="utf-8")
        written.append(output)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("templates", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--corner", default="tt", choices=("tt", "ff", "ss", "fs", "sf"))
    parser.add_argument("--lengths", default="0.15,0.30,0.50,0.80,1.00")
    args = parser.parse_args()

    lengths = [float(item) for item in args.lengths.split(",")]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_deck = find_model_deck()
    print(f"Using SKY130A model deck: {model_deck}")
    for template in args.templates:
        for output in render_template(template, args.output_dir, model_deck, args.corner, lengths):
            print(f"Rendered {output}")


if __name__ == "__main__":
    main()
