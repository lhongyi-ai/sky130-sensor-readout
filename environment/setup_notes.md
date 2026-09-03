# Environment Setup Notes

**Status:** Day 1 schematic-level toolchain verified on this machine.  
**Day 1 gate:** Passed on 2026-09-03.

## Verified toolchain

The reproducible path is the official IIC-OSIC-TOOLS container running through
Colima and the Docker CLI on Apple Silicon. It provides:

- SKY130A PDK;
- Xschem for schematic capture and netlisting;
- ngspice for DC, AC, transient, noise, and corner simulation;
- Magic, KLayout, and Netgen for optional layout/DRC/LVS work.

The Day 1 gate verified the Xschem-to-SPICE path, SKY130A model resolution,
ngspice execution, and retained numeric output. Magic, KLayout, and Netgen were
version-checked but are not needed until optional physical-design work.

## Host preparation

1. Install and start Colima with the Apple Virtualization Framework (`vz`),
   ARM64 guest architecture, Docker runtime, and VirtioFS file sharing.
2. Use the Docker CLI to reach the Colima engine.
3. Clone IIC-OSIC-TOOLS at the recorded commit under the workspace `.tools/`
   directory.
4. Pull the recorded `hpretl/iic-osic-tools` image digest.
5. Run `./scripts/start_eda_desktop.sh`. It uses the upstream VNC workflow,
   binds noVNC and VNC only to `127.0.0.1`, and maps this project to
   `/foss/designs` inside the persistent desktop container.
6. Run `./scripts/run_day1.sh` for the non-interactive characterization gate.

The desktop container name is `sky130-two-stage-ota-vnc`; its local noVNC URL
defaults to `http://localhost:8080/`. The batch script uses an ephemeral
container and mounts this repository at
`/foss/designs/sky130-two-stage-ota`.

## Verification checklist

- [x] Colima Docker engine is running.
- [x] The selected ARM64 container image starts successfully.
- [x] The host design directory is writable from inside the container.
- [x] SKY130A is selected and its model/symbol paths resolve.
- [x] Xschem resolves the SKY130 symbols in the official `test_inv.sch` example.
- [x] Xschem produces a SPICE netlist from that PDK example.
- [x] ngspice runs the generated netlist to completion and writes data.
- [x] Independent NFET/PFET and current-mirror sweeps produce plausible curves.
- [x] Magic, KLayout, and Netgen binaries execute and report versions.

Only the first eight checks are required for schematic-level work; the physical-
design tools are required only for the optional layout stretch.

## Recorded versions and revisions

| Component | Version / revision | Verification command or source | Status |
|---|---|---|---|
| Host OS | macOS 26.5.1 (25F80), Apple Silicon ARM64 | `sw_vers`; `uname -m` | VERIFIED |
| Colima | 0.10.3 (`vz`, ARM64, Docker, VirtioFS) | `colima version`; runtime status | VERIFIED |
| Docker CLI / Engine | CLI 29.7.2; Engine 29.5.2 | client/server version output | VERIFIED |
| IIC-OSIC-TOOLS image | label `2026.08`; index digest `sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`; ARM64 manifest `sha256:65852976cad4af640c9d848762215137e87ec125111a6d06c850c3ab4e9695fb` | image pull/inspect | VERIFIED |
| IIC-OSIC-TOOLS source | commit `db8e081b66e8b0fa22ffd1fc176154c30538ddd0` | Git revision | VERIFIED |
| SKY130A PDK | revision `026824c7969ce6f4fc9678e6ca04b0a06a596c4b` | resolved Ciel/Open PDK path | VERIFIED |
| Xschem | 3.4.8RC | container version output | VERIFIED |
| ngspice | 47 | container version output and completed simulations | VERIFIED |
| Magic | 8.3.681 | container version output | AVAILABLE, NOT USED FOR RESULTS |
| KLayout | 0.30.11 | container version output | AVAILABLE, NOT USED FOR RESULTS |
| Netgen | 1.5.323 | container version output | AVAILABLE, NOT USED FOR RESULTS |

`scripts/run_day1.sh` pins the image by the index digest above so a later moving
`latest` tag cannot silently change the Day 1 runtime.

## Xschem/ngspice smoke test

The source schematic was the PDK-provided
`/foss/pdks/sky130A/libs.tech/xschem/sky130_tests/test_inv.sch`. The first
headless netlist attempt failed because the container's unrelated default PDK
was `ihp-sg13g2`; the generated deck consequently referenced a nonexistent
IHP-relative path for `sky130.lib.spice`. That failure is retained in
`results/smoke/xschem/ngspice_failed_default_pdk.log`.

The fix was to set `PDK_ROOT=/foss/pdks`, source the project `.designinit`, and
pass the SKY130A Xschem `xschemrc` explicitly. The corrected deck includes:

```spice
.lib /foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice tt
```

Xschem then netlisted the example successfully. ngspice 47 completed both
analyses in the example (7,520 and 1,520 rows) and ended with `ngspice-47 done`.
The corrected generated deck and logs are retained under
`results/smoke/xschem/`.

## Day 1 reproducibility manifest

The full batch writes `results/day1_reproducibility_manifest.json`. Its log
validator reports `PASS` after checking all 11 ngspice logs for exactly one
181-row completion marker, exactly one `ngspice-47 done` marker, no fatal or
convergence diagnostic, and no warning except the documented multiplier-
hierarchy warning (11 accepted occurrences). The manifest records 45 SHA-256
digests across authored inputs, rendered netlists, and retained run outputs,
along with host/container versions, the PDK revision, and the model-deck hash.

Sweep-derived compliance endpoints are grid-quantized: the Day 1 voltage step
is 10 mV, so reported interval boundaries carry that resolution rather than
implying a continuous-limit search.

## Smoke-test evidence to retain

- source schematic path and generated netlist;
- simulator log, including the retained initial failure;
- raw Day 1 waveform/data tables;
- `results/day1_reproducibility_manifest.json` with validation status and
  SHA-256 records;
- container digests, PDK revision, and tool versions;
- host-to-container design-directory mapping.

## Reproducibility cautions

- Do not commit proprietary PDK or licensed tool files.
- Do not assume a container tag is immutable; record its digest when possible.
- Keep project sources in the persistent host-mapped directory.
- The clean smoke test and full `./scripts/run_day1.sh` batch have both
  succeeded from the recorded setup. Future tool or PDK changes require a fresh
  smoke test before numerical comparisons.
- Tool and PDK changes must be logged before comparing numerical results.
