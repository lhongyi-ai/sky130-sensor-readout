# Frontend repair experiments: 2026-09-10

This round continues amplifier repair with open-source tools, without waiting for Cadence. It is not a fully qualified frontend, much less a performance report for a complete chip.

Final addition: the same-source G16 **45-point process/voltage/temperature static screen completed all points, with 30 passes and 15 failures**. The worst case was SF / 1.98 V / 85 °C at 457.828 LSB. See the [complete static index](qualification_g16_pvt/20260910T065530849637Z/summary.json). Nominal improvement does not mean cross-temperature/voltage closure, and these 45 points at one gain are not three-gain full-chain verification.

## What is being repaired?

The frontend has two outputs. Their voltage difference is the useful signal, while their average voltage is common mode. Under some conditions, the old candidate lets this average oscillate, affecting downstream ADC readings.

The circuit already has common-mode feedback to restore the average voltage to the proper level. However, current sources are not ideal: their current changes slightly with voltage. Another feedback path may amplify this change. This round therefore tries longer tail-current-source transistors, additional cascode transistors with low-voltage headroom, and adjustments to common-mode sensing and compensation. These are causes proposed and tested from the circuit and waveforms, not unproven inferences presented as settled conclusions.

Cascode transistors can stabilize current but need extra operating-voltage headroom. Gain 1 permits larger input swings, which may reduce that headroom. Progress at gain 16 cannot be assumed to establish passes at gains 1 and 4.

## A recorded same-source candidate: progress and failures

The example below strictly corresponds to core-circuit hash `564f4776c4c61872de63648816ef5aaf51555769edeca326042f287880ae1a3c`. It does not combine the best results from different candidates. Conditions are TT, 1.8 V, 27 °C; noise and sampling use a 2.6 kΩ isolation resistor and 4 pF storage capacitor per side. DC calibration has no switching actions and is a separate test from sampling.

| Test | Recorded result | What it establishes / does not establish |
|---|---|---|
| Gain-16 DC linearity | Maximum residual at independent static input points approximately 0.8194 LSB after three-point linear calibration | Passes this local DC screen; excludes ADC, random noise, and temperature/voltage drift |
| Gain-16 static noise | Output RMS over 1 Hz–1 GHz approximately 111.666 µV; approximately 111.930 µV after multiplying by the same-source nominal calibration factor 1.0023632 | Continuous-time noise with a static load; not sampled SNDR, and not evidence that oscillation has disappeared |
| Gain-16 acquisition endpoint | Worst dynamic residual across three observation points approximately 42.974 µV | Meets the approximately 48.828 µV threshold at these three observation points |
| Gain-16 local turnoff behavior | Worst local post-turnoff residual approximately 41.700 µV | Checks only local instants immediately after turnoff; does not establish the complete conversion hold interval |
| Frontend power | Static frontend VDD power in the noise test approximately 1.806 mW | Excludes the complete ADC, digital control, and real clock drivers; not full-chip power |
| Gain-1 real switched load | Simulation completed, but dynamic error and common mode failed | The same-source candidate cannot be declared complete at all three gains |
| Gain-4 real switched load | `Timestep too small` at approximately 22.479 µs; the 40 µs simulation did not complete | Numerical failure/incomplete, not success; this alone also does not prove inevitable physical circuit failure |

All corresponding raw directories are under `qualification_cas65_deg1000_cap1/`. Other isolation resistances, tail-device dimensions, and subsequent candidates are preserved separately. Improvement in a new version cannot overwrite failure records for the version in this table.

This candidate's scalar loop measurements also have a diagnostic issue: low-frequency common-mode return phase is near −180°. A large phase margin at one differential/common-mode crossing does not establish multiloop stability. Tests with actual switched loads still need independent passes at all three gains.

## Why a sampling pass is not a full-ADC pass

The four-MOS switches here do use SKY130 device models. Terminal A connects to the frontend output, or to VCM for test reset; terminal B connects to the charge-storage capacitor, with compensation transistors attached at B. Two switch groups are replaced, input sampling and test reset, totaling four instances.

However, the test still uses ideal complementary clocks, one equivalent capacitive load, and test reset. It checks only acquisition endpoints and voltages immediately after switch turnoff. Test reset shortens hold time to approximately 5.52 µs, omitting the SAR's full approximately 7.5 µs conversion-hold interval, all bit-by-bit reference switching, comparator kickback, and sampling noise. Therefore `full_conversion_hold_qualified`, `full_frontend_qualified`, and `full_chip_qualified` must all remain false.

## Viewing all attempts rather than only successful screenshots

The following summary command starts no circuit simulation and modifies no old results:

```sh
python3 v2/analog/frontend/repair_20260910/build_summary.py
```

It updates this directory's `repair_summary.json`, indexing `results/*/` and `qualification*/*/`:

- Groups by the actually saved core-circuit hash, while retaining each experiment's gain, isolation resistance, load, stimulus, and solver conditions separately.
- Retains failed thresholds, simulation errors, running experiments, and experiments with circuit files but no summary; absence of results does not imply no work was done.
- Lists original reports separately from reanalysis reports under `analyses/`, without silently replacing original evidence with new reports.
- Uses nominal calibration for noise scaling only when circuit, gain, and process corner match; it does not select the best results from different candidates.
- While root-directory scripts are adding experiments, the index is only a snapshot at generation time and should be rerun after work concludes.

New-format experiments contain `evidence_manifest.json`, covering configuration, the actually simulated circuit, data, logs, source snapshots, and calibration copies. Reanalysis first checks whether those records changed. Records without a manifest are labeled `LEGACY_UNVERIFIED_NO_MANIFEST`: their results and source hashes remain viewable, but they cannot be retrospectively presented as evidence that passed the new integrity checks. Hash checks protect record consistency, not circuit-performance qualification.

## Work that still cannot be declared complete

Stability, full-range settling, noise, linearity, and temperature/voltage behavior are not yet all complete at three gains on one frozen version. Integration with the real full ADC chain, mismatch statistics, and analog-core post-layout simulation remain. Target numbers, local tests, and software-test counts are not presented as measured chip performance.
