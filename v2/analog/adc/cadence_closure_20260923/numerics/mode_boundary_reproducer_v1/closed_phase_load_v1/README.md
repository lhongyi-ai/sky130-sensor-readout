# Closed native phase/load first-edge diagnostic

This is a smaller closed physical subnetwork, not a one-transistor test and not ADC conversion qualification. It retains 654 exact native instances: all 48 phase-generator instances and 606 sampling/switch/CDAC instances. All 104 original CONV gate loads are connected through their complete original transistor networks; CONV remains a free output. Original PDK body/junction models are unchanged. No guessed ideal load capacitor is added.

The 44 preamp and 43 comparator instances are omitted. Their loading on the CDAC top plates and history therefore differ from full ADC. This reduction must reproduce the original first-edge behavior before it is used for causal attribution. It cannot prove the complete ADC is accurate.

The first command is 0 V until 4.0625 us, then rises continuously in 1 ns to 1.8 V, matching the existing native probe source to 2.423 pV at its saved points. All 12 trial bits were exactly 0 throughout that probe. The diagnostic replaces those boundary equations with ideal finite command and DC bit sources, and stops at 4.1 us. Expected complete frames: zero. The original 350 ohm input sources, 1 ohm reference feeds and external 10 nF reference decoupling are retained. Their currents do not define chip input power.

Root scheduler, in the school's configured environment:

```bash
bash run_case.sh baseline 180
bash run_case.sh strict 180
```

Run sequentially. Every invocation retains a new result directory and actual exit status, including timeout. Baseline/strict differ only by requested reltol/vabstol/iabstol reduced tenfold and maxstep 2 ns/1 ns. Both use conservative, sigglobal, gear2only, lteratio=10 and TT/27 C. Check actual precision headers (installed conservative multiplies requested reltol by 0.1). No cmin/gmin/initial-condition/model changes or forced breakpoints.

`verify_inputs.py` checks exact normalized hashes for all retained instances and all input files. `manifest.json` records each instance, omitted names, fanout, original source hash and the diagnostic scope. New saves include CONV driver int_b/dbnode/sbnode, vds, reversed and total terminal currents, using fields already validated on the school's Spectre21.

Review all original accepted points and warnings, compare first-edge timing/body response against the original full-ADC probe, and compare baseline/strict without time alignment or edge removal. A smaller-block success is diagnostic only; complete ADC accuracy remains false until its original protocol and 0.05 LSB numeric criterion pass.
