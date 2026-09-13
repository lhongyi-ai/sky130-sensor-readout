#!/usr/bin/env python3
"""Generate -> DRC -> LVS -> capacitance extraction -> AC smoke simulation.

This is open-tool qualification on two simple primitives, not M0 Cadence
qualification and not DRC/LVS/PEX on the chip. No interconnect resistance
extraction or foundry signoff is claimed.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
PDK = Path(os.environ.get("SKY130_PDK", "/foss/pdks/sky130A"))


def main():
    out = HERE / "results" / ("physical_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True)
    latest = HERE / "results/physical_qualification.json"
    report = {"status": "RUNNING", "cadence_qualified": False, "chip_qualified": False,
              "run": str(out.relative_to(HERE)), "checks": {}}
    latest.write_text(json.dumps(report, indent=2) + "\n")
    env = dict(os.environ, PDK_ROOT=str(PDK.parent), SKY130_PRIMITIVE_OUT=str(out),
               SPICE_USERINIT_DIR=str(PDK / "libs.tech/ngspice"))

    def run(label, command):
        result = subprocess.run(command, cwd=out, env=env, capture_output=True, text=True, timeout=180)
        content = result.stdout + result.stderr
        (out / (label + ".log")).write_text(content)
        return result.returncode, content

    rc, log = run("magic", ["magic", "-dnull", "-noconsole", "-rcfile", str(PDK / "libs.tech/magic/sky130A.magicrc"), str(HERE / "primitive_layout.tcl")])
    report["checks"]["magic_completed"] = rc == 0
    report["bbox_magic_internal_units"] = {}
    for kind in ("mim_unit", "nfet_unit"):
        count = re.search(rf"DRC_COUNT {kind} (\d+)", log)
        report["checks"][kind + "_drc_zero"] = count is not None and int(count[1]) == 0
        bbox = re.search(rf"CELL_BBOX {kind} ([\d. -]+)", log)
        report["bbox_magic_internal_units"][kind] = list(map(float, bbox[1].split())) if bbox else None
        netlist = out / (kind + "_reference.spice")
        if kind == "mim_unit":
            netlist.write_text("* Independent intended primitive connectivity\n.subckt mim_unit C2 C1\nXC C1 C2 sky130_fd_pr__cap_mim_m3_1 w=3 l=3\n.ends\n")
        else:
            netlist.write_text("* Independent intended primitive connectivity\n.subckt nfet_unit B D S G\nXM D G S B sky130_fd_pr__nfet_01v8 w=2 l=1\n.ends\n")
        rc, lvs = run(kind + "_netgen", ["netgen", "-batch", "lvs", f"{kind}_lvs.spice {kind}",
            f"{kind}_reference.spice {kind}", str(PDK / "libs.tech/netgen/sky130A_setup.tcl"), f"{kind}_lvs.log"])
        detailed = (out / f"{kind}_lvs.log").read_text() if (out / f"{kind}_lvs.log").exists() else ""
        report["checks"][kind + "_lvs_match"] = rc == 0 and "Circuits match uniquely." in detailed
    probe = out / "pex_probe.spice"
    probe.write_text(f"""Primitive schematic versus capacitance-extracted AC qualification
.lib {PDK}/libs.tech/combined/sky130.lib.spice tt
.include mim_unit_pex.spice
.include nfet_unit_pex.spice
VSUB VSUBS 0 0
VCAP top 0 AC 1
XC 0 top mim_unit
VDS drain 0 0.9
VGS gate 0 DC 0.9 AC 1
XN 0 drain 0 gate nfet_unit
.control
set num_threads=1
set numdgt=15
op
let extracted_nfet_id=-vds#branch
print extracted_nfet_id
ac lin 1 1000 1000
let extracted_mim_c=-imag(vcap#branch)/(2*pi*1000)
print extracted_mim_c
quit
.endc
.end
""")
    rc, log = run("pex_ngspice", ["ngspice", "-b", str(probe)])
    values = {}
    for key in ("extracted_nfet_id", "extracted_mim_c"):
        match = re.search(rf"^{key}\s*=\s*([-+\deE.]+)", log, re.MULTILINE)
        values[key] = float(match[1]) if match else None
    report["measured"] = values
    report["checks"]["capacitance_extracted_simulation"] = rc == 0 and all(v is not None and v > 0 for v in values.values())
    report["status"] = "OPEN_PRIMITIVE_PHYSICAL_PASS" if all(report["checks"].values()) else "FAIL"
    report["limitations"] = ["Only two primitive cells, not any complete analog or digital block.",
        "Capacitance extraction only; interconnect resistance and complete post-layout circuit performance remain unverified.",
        "Magic/Netgen open rule decks, not Cadence or foundry signoff.",
        "Bare MIM 3x3 um plate is not full cell/array/core area."]
    report["artifact_sha256"] = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    latest.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "checks", "measured", "run")}, indent=2))
    return 0 if all(report["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
