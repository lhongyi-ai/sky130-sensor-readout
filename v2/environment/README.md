# Open-source Environment Qualification and Reproduction Boundaries

Cadence was deferred at the user's request. Evidence in this directory belongs to open-source tools and the public SKY130A PDK, not Cadence qualification.

Original qualification used the IIC-OSIC-TOOLS image `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`, with the PDK installed at container path `/foss/pdks/sky130A`, resolved revision `026824c7969ce6f4fc9678e6ca04b0a06a596c4b`. The historical container name was `sky130-v2-open-work`; historical records are retained.

The actual 2026-09-10 runtime container was `sky130-v2-resume-20260910`, using the same image and PDK with networking disabled. The complete working copy is at `/Users/stanley/Documents/ChatGPT/Analog Circuit Project/sky130-two-stage-ota`; its root is mounted read-only at `/repo`, with only the new-version directory mounted writable at `/repo/v2`. New runs neither write the old working copy nor start Cadence.

Additional finding: available VACASK runs intrinsic RC random noise, but its BSIM4v8 noise is not equivalent to the SKY130 BSIM4v5 selected by current ngspice47, so qualification fails. See [Noise qualification from this round](../verification/noise_20260910/README.md); installed software does not imply usable process noise.

## Independent qualifications executed

| Entry point | Evidence | Scope |
|---|---|---|
| `qualify.py` | [device_qualification.json](results/device_qualification.json) | 45 single-device process/voltage/temperature points, 200 real mismatch instances, repeated/disabled statistical seed controls; 247 simulations total |
| `qualify_cap_multiplier.py` | [cap_multiplier_qualification.json](results/cap_multiplier_qualification.json) | 600 real PDK capacitor instances, checking means and local-mismatch scaling for a unit, m=64 only, and m=mult=64 |
| `qualify_physical.py` | [physical_qualification.json](results/physical_qualification.json) | Self-generated small MIM and NMOS layouts, DRC/LVS, and a simulation closed loop including capacitive parasitics |

Reproduce by invoking the corresponding Python script in that container. Each run generates a timestamped output directory, source snapshots, raw simulation files, logs, and a structured report.

Actual finding: MIM `m=64` alone correctly scales nominal capacitance, but does not justify assuming local random mismatch shrinks by sqrt(64). Independent control experiments verify correct local statistical scaling with `m=64 mult=64` in this PDK. Failure reports for the original incorrect assumption are retained, not overwritten.

These 200 samples check devices or capacitor constructions, not yield for 200 complete chips. The statistical model has not verified spatial gradients or layout-dependent systematic mismatch. Extraction in the small-layout closed loop covers capacitive parasitics; [Sampling-switch physical implementation](../physical/adc_switch/) and the digital macro have separate real RC extraction and must not be conflated.

Only project-owned designs, tool/model revisions, hashes, results, and necessary publicly shareable licensing notes are retained; restricted rules, licenses, accounts, and school configuration are not copied.
