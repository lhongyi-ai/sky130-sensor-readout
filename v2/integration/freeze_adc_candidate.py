#!/usr/bin/env python3
"""Freeze LVT reference + dummy-clamp ADC without modifying prior candidates."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    folder = HERE/"candidates"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True)
    paths = [ROOT/"analog/adc/adc_blocks.spice",ROOT/"analog/adc/adc_preamp.spice",
             ROOT/"analog/adc/adc_reference_candidate.spice",
             ROOT/"physical/adc_switch/candidates/adc_tgate_dual_lvt_dummy.spice",
             ROOT/"analog/adc/adc_analog12_bottom_preamp_lvtref.spice"]
    hashes = {}
    for source in paths:
        data = source.read_bytes()
        (folder/source.name).write_bytes(data)
        hashes[str(source.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    wrapper = (folder/paths[-1].name).read_text()
    for net in ("P","N"):
        old = f"XS{net} VCM T{net} SAMPLE SAMPLEB VDD VSS adc_tgate"
        if wrapper.count(old) != 1:
            raise ValueError("sampling interface changed; review the topology before replacing it")
        wrapper = wrapper.replace(old,old.replace("adc_tgate","adc_tgate_dual_lvt_dummy")+" WN=4 WP=8")
    old_name = "adc_analog12_bottom_preamp_lvtref"
    name = "sensor_adc_candidate"
    wrapper = wrapper.replace(".subckt "+old_name+" ",".subckt "+name+" ").replace(".ends "+old_name,".ends "+name)
    (folder/"sensor_adc_candidate.spice").write_text(wrapper)
    report = {"status":"UNQUALIFIED_INTEGRATION_CANDIDATE","full_chip_qualified":False,
              "source_sha256":hashes,"derived_wrapper_sha256":hashlib.sha256(wrapper.encode()).hexdigest(),
              "subckt":name,"notes":["Same bottom-sampling/retained-comparator phase and code polarity.",
                "Only the two top-to-VCM clamps use the four-MOS dummy-cancelled sampling switch; dummy diffusions attach to held top nodes.",
                "Reference/ACQ branches use the separate non-dummy LVT candidate, with bit-weight-dependent widths.",
                "Standalone switch and reference results do not qualify this combined ADC. Real phase load, charge injection, dynamic code behavior and all PVT remain required."]}
    (folder/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print(str(folder))


if __name__ == "__main__":
    main()
