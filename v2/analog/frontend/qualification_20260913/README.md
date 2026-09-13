# Local verification progress for the revised frontend (2026-09-13)

Verification methods and noise evidence for the same `candidate_06.spice` have advanced, but **formal multiloop stability, sampled noise, and 45-PVT coverage remain incomplete**. This round changes neither the circuit, thresholds, nor existing evidence from 2026-09-11.

The authoritative status is `qualification.json`. Source SHA-256: `a4ed567d6a5b1f8853124602fd3f0503118e77c751a6fc3152f772b89483a5f1`. All simulations use the same source and actual SKY130 devices, 350 Ω source impedance per side, 1.5 kΩ isolation, 4 pF filtering, and a 4096-cell MIM sampling load. Environment hashes and 216 recursive model-dependency hashes are in `environment.json`.

## Work actually completed in this round

26 serial ngspice launches: 6 local dual-injection cases, 6 four-plane coupled-matrix cases, 6 valid noise cases, 1 closed-loop pole attempt, 1 minimal connectivity test for migration, and 6 fully retained noise-export failures. Each directory contains circuit/testbench snapshots, raw numerical data, logs, exit codes, analysis status, and a SHA-256 manifest. All new files are confined to this directory.

### The old high-frequency upward crossing was mainly a measurement-method issue

The old voltage ratio ignored reverse transmission and loading at the measurement port. This round adds zero-DC voltage and current sources into the normal DC connections and uses two AC excitations to obtain a local bidirectional return ratio, while the other real loops remain closed. The old differential second 0 dB upward crossings near 38.9–74.8 MHz disappear in all six gain/switch-state combinations.

| State | G1 local differential PM | G4 local differential PM | G16 local differential PM |
|---|---:|---:|---:|
| Acquisition switch held on | 81.79° | 81.91° | 81.96° |
| Acquisition switch held off | 74.22° | 81.21° | 87.33° |

This is a local-loop diagnostic. The first-stage common-mode low-frequency return-sign anomaly remains at G1/G4; neither this table nor independent-loop PM establishes full multiloop signoff.

The dual-injection formula uses the bidirectional two-port analysis in the [original paper by Tian et al.](https://kenkundert.com/docs/cd2001-01.pdf), subject to its applicability conditions. No single critical wire that breaks all feedback was found here, so a single-probe result is not promoted to a global proof.

### The coupled return difference is calculated, with explicit gaps in formal signoff

The four measurement planes are differential input, common-mode input, first-stage common mode, and output common mode. Separate current/voltage excitations provide the complete A/B/C/D cross-responses, from which port admittance K is reconstructed and `det(K)/det(Yee+Yff)` calculated. Raw matrices are in each `coupled_hybrid_matrices.npz`, and return-difference curves are in `coupled_return_difference.csv`.

Across six cases, the maximum algebraic matrix-reconstruction residual is approximately 2.09e−16, and the maximum C-matrix condition number is approximately 5021. This residual checks only algebraic matrix reconstruction; **it is not an eigenvalue residual of the original transistor Jacobian**. The reference admittance still contains active devices, and no reliable right-half-plane pole count exists. Internally unobservable modes have not been excluded, and a 1 GHz endpoint does not automatically replace an infinite-frequency contour. No Nyquist winding-number or global-PM pass is claimed.

### Same-source static noise exposes real design pressure

The table below gives continuous-time small-signal noise over **1 Hz–1 GHz at the FP−FN output, multiplied by the same-source three-point calibration slope**. Switches are fixed in each state, excluding periodic switching, noise folding, and real ADC conversion noise.

| Fixed state | G1 | G4 | G16 |
|---|---:|---:|---:|
| Acquisition | 71.43 µVrms | 151.17 µVrms | 431.74 µVrms |
| Hold | 128.07 µVrms | 243.77 µVrms | 536.06 µVrms |

The 113 µV provisional static output budget comes from the old `build_frozen_summary.py`, whose FDDA10 used 2.8 kΩ isolation. This round uses a resistive-input PGA, 1.5 kΩ isolation, and explicitly fixed sampling states, so the test assemblies differ. Comparing this table with 113 µV is diagnostic only; formal noise PASS/FAIL remains unset, and the comparison cannot declare the system's 65 dB SNDR qualified or failed. Integrals over 1–5 kHz and 1–50 kHz are also fully retained, but narrowing bandwidth cannot substitute for broadband/sampled-noise qualification.

The first 6 noise runs solved correctly but reported `no such vector onoise_spectrum` because the wrong current plot was read. All six original failures and exit code=0 are retained, while analysis status remains failed. Repeating the original stimulus with explicit selection of `noise1` succeeded. The runner now stops immediately on this type of failure. Process exit 0 alone cannot establish successful result export.

### Complete closed-loop PZ is not yet usable evidence

Native `pz fp 0 fp 0 cur pol` at G1 acquisition exited normally and returned 354 roots, including 239 labeled right-half-plane by the algorithm. The root count/distribution and existing stable transients present a discrepancy requiring explanation; residual, model-order, and mode-completeness audits remain incomplete. The raw root list is retained without alteration. Unverified roots are neither used to declare real instability nor deleted to claim stability. The [official ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-42-manual.pdf) explains that this search method may miss roots or return too many. No repeated port changes were attempted without new evidence.

## Reproduction and migration

Inside the qualified local IIC-OSIC container at `/repo/v2/analog/frontend/qualification_20260913`:

```sh
python3 run_qualification.py local --gains 1 4 16 --states acquire hold
python3 run_multiport.py
python3 run_qualification.py noise --gains 1 4 16 --states acquire hold
python3 run_qualification.py pz --gains 1 --states acquire --timeout 45
python3 run_canary.py
python3 build_report.py
python3 -m unittest discover -s . -p test_qualification.py -v
```

Every run creates a new timestamped directory. The actual driver scripts for the multiport and minimal tests are separately saved in that run's `*_driver_snapshot.py` and `supplemental_provenance.json`, without rewriting original manifests. The complete `delivery_manifest.json` covers every delivered file.

6 meaningful checks passed: a known bidirectional two-port, passive zero return, independent nondiagonal multiport admittance reconstruction, byte-identical candidate source, all evidence hashes/conservative statuses, and agreement between noise-density integration and the simulator's built-in integral for all six cases (relative deviation <0.1%). They validate method implementation and file integrity, not formal circuit qualification.

University-migration interfaces and the minimal test are in `CADENCE_CANARY.md`. This round makes no claim of a university launcher, upload package, remote run, or completed native import. Next, obtain reliable complete multiloop pole/contour evidence and modify the circuit to address G4/G16 noise pressure. After changes, restart nominal dynamic verification at all three gains on the same version. The formal stability requirement remains unresolved, so 45-PVT was not started.
