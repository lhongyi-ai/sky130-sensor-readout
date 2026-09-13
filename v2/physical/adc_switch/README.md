# SAR Sampling Switch: Real Devices, Independent Layout, and Failed Iterations

This directory does not use Cadence. It verifies one input sampling switch, not layout,
linearity, noise, or accuracy acceptance for the complete SAR ADC or readout chip.

## Final frozen results

**The independent four-transistor sampling switch passes verification under specified conditions.**
The formal entry point is `results/sampling_switch_release.json`; see `SOURCE_INDEX.md` for files and ports.
Final parameters: main N-LVT 4/0.15µm, P-LVT 8/0.35µm, compensation transistors at half width each.

| Verification item | Result |
|---|---|
| Physical layout | DRC=0, unique LVS match, real extraction of 95R/51C |
| Actual cell boundary/area | 16.0×17.295µm, 276.72µm² |
| Full grid | 45PVT×3 inputs×3 common modes×3 driver resistances×2 views=2430 condition points, 0 failures |
| Window/load | 2.476847754µs acquisition, hold through 10µs, 81.28512pF/terminal |
| Worst schematic acquisition/final-hold error | 10.94µV / 30.76µV |
| Worst post-RC acquisition/final-hold error | 13.66µV / 26.15µV |
| Opposite-full-scale initial-state boundaries | All 216 condition points at 4 explicit PVT points pass; worst acquisition 22.15µV |

Every acquisition/hold error above is below the 48.828125µV checking threshold. The full grid places
electrically independent copies in 45 transient batches; these are **not 2430 independent simulation
commands or random yield samples**. The 4 full-scale boundary PVT points are not portrayed as another 45PVT run.
`qualify_release.py` rereads all 45 batches of raw waveforms, checking full duration, finite values,
monotonic time, and per-point measurements, and checks the grid item by item. All compressed waveforms remain in `evidence/`.

Ideal 1ns complementary clock edges are still used; the acquisition window comes from a conservative
measurement of the real phase generator. The system still needs actual clock loading/skew, real
bottom-plate switching, noise, and ADC nonlinearity verification. This is neither a full-ADC pass nor Cadence/silicon evidence.

## Frozen standard-threshold baseline

The original circuit is `adc_tgate A B EN ENB VDD VSS`: standard NFET W/L=8/0.15µm,
standard PFET W/L=16/0.15µm. Real SKY130 PCell layout with body contacts/guard rings,
metal routing, and ports was generated, with Magic DRC=0 and unique Netgen LVS match.
After flattening, a new Magic process extracted 42 resistors and 29 positive capacitors;
no fake resistors or schematic-only capacitance substitute for RC extraction. Files are in `artifacts/`.

With 2.5µs acquisition and a 4096×3µm×3µm MIM load, 45PVT×3 inputs plus additional
nominal 0/1kΩ source impedances completed 141 schematic/RC pairs, or 282 simulations.
**14 view-cases fail**, with worst RC acquisition residual approximately −37.4mV at
SF/1.62V/−20°C, input 1.01V. The schematic also fails because both transistors have
insufficient conduction at low supply and temperature; this is not a problem appearing only after extraction.
Passing DRC/LVS cannot be described as the sampling switch meeting system accuracy.

Complete raw failure table: `results/switch_validation.json`. `run.py` regenerates it and
returns nonzero status for metric failures, without hiding results.

## Independent candidates and completed comparisons

All candidates are in `candidates/`; the ADC owner's `adc_blocks.spice` was not overwritten.

| Candidate | Actual test finding |
|---|---|
| Replace only N with LVT, still W8/P16 | Worst Ron at SS low voltage/low temperature drops from 42.4kΩ to 16.0kΩ, but settling error remains approximately 10mV; insufficient |
| Dual LVT, N8/.15, P16/.35 | Worst Ron falls to approximately 1.26kΩ, but turnoff injection reaches 195µV; speed does not establish accuracy |
| Dual LVT, N4/.15, P4/.35 | Injection decreases, but SS settling residual is approximately 87µV; devices too small |
| Dual LVT, N4/.15, P5/.35 | 140 of 141 points pass in the old 2.5µs window; high-input error of 49.03µV at FS/1.98V/85°C slightly exceeds 48.83µV; not an all-pass result |

The PDK's minimum legal/modeled low-threshold PMOS length is 0.35µm. An early 0.15µm
attempt was rejected directly by the model; logs are retained, without extrapolation beyond model bounds.
Actual AC current confirms MIM load of 81.28512pF; both `m` and `mult` follow verified PDK invocation rules.
After extending to a full 7.5µs hold and reversing external input, old-candidate hold leakage is approximately
0.04µV. The main issues are conduction and turnoff charge, not leakage during this hold interval.

The N4/P5 two-transistor candidate also completed independent physical layout, with boundary
8.155×7.19µm, 58.63445µm², DRC=0, unique LVS match, and 42R/29C. Eighteen schematic/RC
simulations at 9 old-window nominal/extreme-corner points pass, proving only those tested conditions.
See `artifacts/dual_lvt_rc_smoke/` and its PNG for the actual layout render.

## Final window and expanded scope

The shortest acquisition window from the real phase generator is 2.476847754µs; old 2.5µs
results cannot claim coverage of that shorter window. `batch_qualification.py` uses this window,
measures acquisition error 1ns before turnoff starts, and holds through 10µs; input reverses 200ns after turnoff.
Independent copies of the same circuit at each PVT cover inputs −0.2/0/+0.2V, common-mode offsets
−50/0/+50mV, and source impedances 0/350/1000Ω. Batching only reduces repeated PDK loading;
every copy still has its own real MOS devices, MIM load, and source resistor.

350Ω is the frozen main-specification source impedance; 0/1kΩ are additional sensitivity tests.
Reports separately count main-specification and sensitivity failures. The absolute quarter-LSB
post-turnoff check is extra design margin; it replaces neither full-ADC linearity/noise checks nor
validation of frozen-coefficient external calibration. Half-width-dummy versions also remain candidates;
ideal charge cancellation must not be assumed.

Four-transistor ports are **no longer symmetric**: A is the driven-source side, B the held-capacitor/top-plate side.
Both dummy transistors are shorted only to B. If used as a VCM top-plate clamp, A must connect to VCM
and B to the top plate; do not carry over arbitrary A/B interchangeability from the old two-transistor TG.
Clamp behavior under real CDAC bottom-plate switching still requires system simulation and cannot be
replaced solely by A-terminal voltage steps in this directory.

Resistance here sits directly at the standalone sampling-switch input and represents the test driver's resistance.
The system specification's 350Ω sensor source impedance is before the PGA. This test cannot replace
real joint drive analysis of sensor–closed-loop PGA–sampler, and does not claim PGA output resistance is 350Ω.

## Reproduction

Run in `/repo` in the project's existing offline tool container, for example:

```sh
python3 v2/physical/adc_switch/run.py --tag new_standard --suite full
python3 v2/physical/adc_switch/characterize_candidate.py --tag new_lvt --suite full --model adc_tgate_dual_lvt --wn 4 --wp 5
python3 v2/physical/adc_switch/physical_candidate.py --tag new_layout --suite smoke --wn 4 --wp 5
python3 v2/physical/adc_switch/batch_qualification.py --tag new_short_window --suite full --wn 4 --wp 5 --physical-run new_layout
```

These commands reproduce historical two-transistor controls. Complete reproduction for the final four-transistor version is:

```sh
python3 v2/physical/adc_switch/physical_candidate.py --tag dummy_layout_final --suite physical_only --model adc_tgate_dual_lvt_dummy --wn 4 --wp 8
python3 v2/physical/adc_switch/batch_qualification.py --tag dummy_w4w8_rc_full --suite full --model adc_tgate_dual_lvt_dummy --wn 4 --wp 8 --physical-run dummy_layout_final
python3 v2/physical/adc_switch/fullscale_check.py
python3 v2/physical/adc_switch/qualify_release.py
```

These fixed tags suit a fresh clone; do not overwrite existing local runs. Use an independent copy or
update run selection in the review scripts. Postprocessing uses NumPy; final qualification runs only
one simulation worker to avoid competing with other analog tasks for memory.

New tags are required; past raw failure records must not be overwritten. `runs/` stores every input netlist,
log, waveform, and hash, excluded from Git by default; `results/` and selected `artifacts/` are portable evidence.
Install the same public PDK revision; this directory does not copy the PDK, rule files, or license keys.

Remaining system integration includes real clock drive/skew, dynamic CDAC reference switching, matching,
noise, differential ADC linearity, and full-chain accuracy. A standalone switch pass cannot replace these checks.
