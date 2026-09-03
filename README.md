# SKY130 Two-Stage CMOS OTA

Specification-driven design and robustness verification of a 1.8 V, two-stage,
Miller-compensated CMOS operational transconductance amplifier using the
open-source SKY130A PDK.

> **Project status — Day 1 complete; OTA design not yet verified.** The SKY130A
> toolchain and schematic-to-ngspice path passed a smoke test. TT/27 °C NFET and
> PFET characterization, an NMOS current-mirror compliance sweep, and
> characterization-based *initial* sizing candidates are reproducible. The OTA
> schematic, closed-loop simulations, and all OTA performance/PVT fields remain
> `NOT_RUN`; no achieved OTA performance is claimed yet.

## Objective

The project converts hand analysis into a reproducible transistor-level design:

`specification -> device characterization -> sizing -> schematic -> simulation -> PVT verification -> documented tradeoff`

The intended core contains:

- an NMOS differential input pair;
- a PMOS current-mirror active load;
- an NMOS tail-current source;
- an NMOS common-source second stage with a PMOS current-source load;
- Miller compensation, with an optional series nulling resistor;
- an external reference-current input and MOS current mirrors for biasing.

## Frozen specification

Nominal conditions are SKY130A TT, 1.8 V, 27 °C, input common-mode voltage of
0.9 V, and an output load of 5 pF in parallel with 100 kΩ. The 100 kΩ load's
connection must be shown explicitly in every applicable testbench.

| Metric | Hard requirement | Stretch target | Qualification scope |
|---|---:|---:|---|
| Open-loop DC gain | >= 50 dB | >= 60 dB | All 13 core PVT points |
| Unity-gain bandwidth | >= 5 MHz | >= 10 MHz | All 13 core PVT points |
| Phase margin | >= 55° | >= 65° | All 13 core PVT points |
| Quiescent power | <= 600 µW | <= 400 µW | All 13 core PVT points |
| Positive slew rate | >= 2 V/µs | >= 4 V/µs | All 13 core PVT points |
| Negative slew rate | >= 2 V/µs | >= 4 V/µs | All 13 core PVT points |
| 1% settling time | <= 1.5 µs | <= 1.0 µs | Nominal |
| CMRR at 1 kHz | >= 55 dB | >= 65 dB | Nominal |
| PSRR+ at 1 kHz | >= 45 dB | >= 55 dB | Nominal |
| PSRR- at 1 kHz | >= 45 dB | >= 55 dB | Nominal |
| Input common-mode range | Includes 0.8–1.3 V | Maximize | Nominal |
| Output swing | Includes 0.3–1.5 V | Maximize | Nominal |
| Input-referred noise | Measure and report | — | Nominal |

Load stability is additionally checked at TT/1.8 V/27 °C with 1 pF, 2 pF,
and 5 pF loads. The hard criterion is phase margin >= 55° at each load and no
sustained oscillation in the corresponding unity-gain transient response.

The authoritative definitions and pass policy are in
[`docs/specification.md`](docs/specification.md). Targets are not results.

## Five-day execution gates

| Day | Work package | Exit evidence |
|---|---|---|
| 1 | Environment, PDK smoke test, NFET/PFET characterization, current mirror, specification and first calculations | Verified tool versions; runnable PDK device test; characterization plots/data; current-mirror error/compliance data |
| 2 | Bias network and M1–M5 differential stage | Device operating-point table; reasonable saturation headroom; symmetric input currents; first-stage gain and ICMR sweep |
| 3 | Second stage, Miller compensation, nominal tuning | Final nominal A0, UGB, PM, power, and a stable unity-gain transient response |
| 4 | Full characterization and automated 13-point PVT sweep | Raw outputs, parsed summaries, failure-preserving PVT table, and final plots |
| 5 | One documented optimization, final report, and repository polish | Before/after tradeoff, reproducible README, PDF report, limitations, resume bullets, and interview explanation |

Partial layout and DRC/LVS are optional stretch work only after all schematic-
level exit gates have passed.

## Results

### Day 1 evidence

The Day 1 batch run completed at SKY130A TT and 27 °C. Standard-VT 1.8 V NFET
and PFET devices were characterized at `|VDS| = 0.9 V` for channel lengths
0.15, 0.30, 0.50, 0.80, and 1.00 µm. The retained artifacts are:

- [device-characterization plot](results/plots/day1_device_characterization.png)
  and [initial sizing candidates](results/device_sizing_candidates.csv);
- [current-mirror compliance plot](results/plots/day1_current_mirror_compliance.png)
  and [current-mirror summary](results/current_mirror_summary.csv);
- [Day 1 reproducibility manifest](results/day1_reproducibility_manifest.json),
  containing tool/PDK identity, `PASS` log validation, and 45 SHA-256 records;
- raw numeric tables and ngspice logs under `results/raw/day1/`;
- the Xschem-to-ngspice smoke-test netlist and logs under
  `results/smoke/xschem/`.

For the 1:1 NMOS mirror (`W/L = 5/0.8 µm`), the forced reference was 10 µA and
the reference transistor carried 10.0000012 µA at `VOUT = 0.9 V`. The output
current was 10.1780846 µA: 1.78084599% error versus the forced reference, or
1.78083395% versus the measured reference-device current. The model saturation
interval was 0.11–1.80 V; the separately reported interval satisfying
saturation and at most 5% error versus forced `IREF` was 0.28–1.30 V. Interval
endpoints are quantized to the 10 mV sweep grid. These are test-structure
results, not OTA results.

The candidate dimensions derived from the lookup tables are explicitly tagged
`INITIAL_CANDIDATE_NOT_FINAL`. They must still be checked at the actual OTA
operating points and tuned against the frozen closed-loop specifications.

### OTA result status

The OTA result templates remain deliberately unpopulated/`NOT_RUN`:

- [`results/summary.csv`](results/summary.csv)
- [`results/pvt_summary.csv`](results/pvt_summary.csv)

When populated, each reported number must link to a retained raw simulation
output and identify its testbench, process corner, voltage, temperature, and
load. Failed or non-convergent runs must remain visible rather than being
deleted from the summary.

Required final figures are:

1. annotated transistor-level schematic;
2. loop-gain Bode plot with A0, UGB, and phase-margin markers;
3. unity-gain step response with SR+, SR-, overshoot, and settling band;
4. ICMR/output-swing characterization;
5. PVT comparison for gain, UGB, phase margin, power, and slew rate;
6. input-referred noise-density plot (recommended).

## Repository map

```text
sky130-two-stage-ota/
├── README.md
├── LICENSE
├── environment/
│   └── setup_notes.md
├── netlists/
│   └── day1/
│       ├── nfet_characterization.spice.in
│       ├── pfet_characterization.spice.in
│       └── nmos_current_mirror.spice.in
├── scripts/
│   ├── render_netlists.py
│   ├── analyze_day1.py
│   ├── write_day1_manifest.py
│   ├── run_day1.sh
│   └── start_eda_desktop.sh
├── docs/
│   ├── specification.md
│   ├── design_calculations.md
│   ├── architecture.md
│   └── project_log.md
├── schematics/
│   └── README.md
└── results/
    ├── summary.csv
    ├── pvt_summary.csv
    ├── device_sizing_candidates.csv
    ├── current_mirror_summary.csv
    ├── day1_reproducibility_manifest.json
    ├── plots/
    ├── raw/day1/
    └── smoke/xschem/
```

From a running Colima/Docker environment, reproduce all Day 1 characterization
data, summaries, and plots with:

```sh
./scripts/run_day1.sh
```

The script defaults to the recorded IIC-OSIC-TOOLS image digest, renders fresh
SPICE decks from the source templates, runs ngspice in the container, analyzes
the retained tables, validates every successful-run log, and writes the
checksum manifest. To open the locally bound noVNC EDA desktop, use
`./scripts/start_eda_desktop.sh`. Exact
revisions, versions, mount paths, and the smoke-test failure/fix are documented
in [`environment/setup_notes.md`](environment/setup_notes.md).

## Limitations and claims

This is a simulation-based educational IC-design project using an open-source
PDK. It has not been fabricated or measured in silicon. At the current status,
only the Day 1 device test structures and tool flow have verified
schematic-level simulation results; the OTA itself does not.

- Process corners do not model local device mismatch.
- No Monte Carlo run means no mismatch, offset-distribution, or yield claim.
- No extracted netlist means no post-layout performance claim.
- DRC/LVS may be claimed only for a block that actually passes both checks.
- No result may be described as measured; the correct term is simulated.
- No production-qualified, tapeout-ready, or silicon-validated claim is made.

## License

Project-authored material is released under the MIT License. SKY130 PDK files,
models, and third-party EDA tools retain their own licenses and are not
redistributed by this repository.
