# Native SKY130 Noise Closure Check — 2026-09-11

## Conclusion

**The currently installed environment cannot directly complete time-varying device-noise acceptance for the real SAR ADC.**

Status: `BLOCKED_NATIVE_INTRINSIC_SWITCHING_NOISE_UNAVAILABLE`.

This round completed actual capability checks and a strictly bounded sampled-noise planning tool: preserve ngspice native **BSIM4v5 / version 4.5** frequency-domain noise, then perform ideal-sampling folding and statistical checks over a finite frequency band. This is not noisy ADC simulation and cannot pass final SNDR acceptance.

Cadence was not used; simulators/PDK were not downloaded, installed, or modified. VACASK v8 results were not scaled to impersonate v5, and artificial white noise was not injected into circuits. Legacy files and results are unchanged.

## 1. What four small-cell runs actually did

Raw data are in [results/20260911T080040Z](results/20260911T080040Z). Four runs cover RC noise off, on, same-seed replay, and a different seed. Each uses one simulation process and sequentially completes operating point, an 11-point DC sweep, AC, frequency-domain noise at three outputs, and a 2 ms ordinary transient. Each process has a 180-second limit; actual times are 6.46, 6.75, 6.01, and 5.32 seconds. **All simulations in this round have ended; no additional circuit runs are being started.**

Each circuit has three uncoupled parts:

- Native 10 kΩ resistor + 1 nF capacitor, 27 °C.
- A self-compiled minimum Verilog-A resistor + 1 nF, with internal `white_noise(4kT/R)` declaration; this is a control for loading and noise-evaluation capabilities, not a replacement SKY130 model.
- The exact same real SKY130 NFET as on September 10: W = 2 µm, L = 1 µm, gate voltage 0.7 V, supply 1.8 V, 20 kΩ load, 1 pF output load, TT, 27 °C.

### RC and real single-transistor results

| Control circuit | RMS from 1 Hz–100 MHz with frequency-domain noise enabled | Ordinary-transient noise standard deviation | Interpretation |
|---|---:|---:|---|
| Native ngspice RC | 2.035632 µV | 0 V | Resistor frequency-domain noise switch works; no transient thermal noise |
| Verilog-A / OSDI RC | 2.035633 µV | 0 V | `white_noise` works in frequency domain but does not become a transient random device source |
| Native SKY130 BSIM4v5 single-transistor output | 164.057543 µV | Approximately 5.54 × 10⁻¹⁶ V | Numerical rounding fluctuation only; cannot be interpreted as very low noise |

With noise disabled, both RC frequency-domain results are zero; their maximum AC relative error against the analytical RC transfer function is approximately 4.5 × 10⁻¹⁶. With noise enabled, native RC spectral error relative to 4kTR is approximately 3.5 × 10⁻⁷, and OSDI approximately 9.4 × 10⁻⁷. Physical constants differ slightly between implementations; **no empirical scaling was applied**. Comparing interpolated measured-spectrum integration with analytical finite-band integration gives relative error 2.24 × 10⁻⁵.

The real transistor is still evaluated by `xm:nshort_model.29`, **BSIM4v5**, without expanding, deleting, or modifying PDK parameters. Output operating point is 1.718068324769174 V, drain current 4.0965837615413055 µA. Relative to old native results, operating-point current error is 0; maximum AC relative error across 141 common frequency points is 2.48 × 10⁻¹⁴ and noise-power-spectrum error is 4.95 × 10⁻¹⁴. This is not old VACASK v8 noise.

**“On/off” must not be read as enabling/disabling single-transistor time-varying noise.** No usable such switch was found for the native SKY130 transistor; all four runs use the same complete model. Changes affect RC frequency-domain noise declarations and the `notrnoise` variable, which applies only to independent TRNOISE sources. The circuit contains no independent TRNOISE source.

### Seed and command checks

All four transistor transient traces agree point by point; changing seeds generates no device noise. A **software random vector completely disconnected from the circuit** does replay with the same seed and change with a different seed. The issue is therefore absent transient-device-noise evaluation, not a broken seed command.

Actual calls to `noisetran` return `no such command available in ngspice` in all four logs. The wrapper library returns an empty text array, but each error is recorded in `worker.log`; the audit reads logs and does not treat an empty return as success.

Official sources also distinguish these capabilities: ngspice 47 independent TRNOISE sources work in transient, and `notrnoise` controls only those sources; ordinary `.noise` is stationary small-signal analysis and does not establish inclusion of switched-circuit noise. [ngspice 47 manual, §1.2.7, §4.1.7, §11.3.11](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf) OSDI loads Verilog-A models, but loading capability does not imply time-varying noise capability; this round's RC control verifies the distinction. [Official OSDI description](https://ngspice.sourceforge.io/osdi.html) The relevant new feature in the version-47 announcement is small-signal noise for code models, which cannot be extended to native BSIM4 transient noise. [Official release announcement](https://ngspice.sourceforge.io/news.html)

ngspice 47 manual §11.3.11 still lists transient noise from transistor models as unresolved work. Alternative tools are not automatically qualified either: Table 2-36 in the [Current official Xyce 7.10 capability table](https://xyce.sandia.gov/download/2068/?tmstv=1754510749) still does not mark stationary-noise support for BSIM4 level 14/54. The project used `Xyce -v` to freeze local installation identity as `7.10-opensource`, but **did not run an Xyce SKY130 noise circuit**. Identity/documentation checks are not measured transient-noise evidence and cannot establish Xyce as a verified substitute. Earlier [7.7](https://xyce.sandia.gov/files/xyce/Xyce_Reference_Guide_7.7.pdf) and [7.8](https://xyce.sandia.gov/files/xyce/Xyce_Reference_Guide_7.8.pdf) tables are also retained for version-history comparison.

## 2. Newly completed hybrid method: planning only

Implementation: [hybrid.py](hybrid.py); offline analysis: [analyze.py](analyze.py). The flow is:

1. Extract output-noise amplitude spectra from the real native circuit and square them to obtain one-sided power spectral density S(f), in V²/Hz.
2. Use power-law interpolation between measured frequencies and analytical integration; use the logarithmic integral limit for 1/f spectra.
3. For an ideal instantaneous sampler, fold noise power from both sides of every sampling-frequency multiple into 0–fs/2, with fs = 100 kS/s.
4. Allocate integrated power in each folded frequency interval to 16,384-point Fourier coefficients, producing finite-length Gaussian model sequences with the specified spectrum.
5. Check power conservation, same-seed replay, different-seed variation, and mean-square statistical error over 128 model-noise sequences.

For baseband interval [a,b], the power-folding relationship is:

`Psample[a,b] = ∫[a,b] S(f)df + Σ(k≥1){∫[kfs+a,kfs+b] S(f)df + ∫[kfs−b,kfs−a] S(f)df}`

Only **contributions from the available 1 Hz–100 MHz spectrum** are integrated. Noise outside this range is marked unknown, not physically zero. Power summed over all sampled-frequency intervals must equal the integral over the same known analog band; RC relative error is approximately 2.2 × 10⁻¹⁶ and transistor error is 0. Additional unit tests independently check against the spectrum of exact sampled RC covariance `kT/C × exp(−|lag|Ts/RC)`.

The model's DC Fourier component is a random record mean, so total power uses **mean square**; do not subtract the mean before comparison with full-spectrum power. This is not the project's offset-calibration model.

| Planning example for known-band contributions | Direct integration over 0–5 kHz | After ideal-sampling folding into 0–5 kHz |
|---|---:|---:|
| 10 kΩ / 1 nF RC | 0.8960 µV RMS | 0.9332 µV RMS |
| Same fixed-bias SKY130 transistor output | 58.7595 µV RMS | 74.6769 µV RMS |

This shows that ignoring folding can underestimate noise. **None of these values are sensor-frontend or complete-ADC results.** The transistor is only a capability-check circuit at specified load and bias.

Across 128 noise sequences for each model, average mean square differs from theoretical expectation by 0.067 and −0.444 standard errors respectively. These are **noise realizations, not PDK process/device-mismatch Monte Carlo**. Mismatch sample count remains 0; the 128 sequences cannot count toward the project's required 200 mismatch samples.

## 3. Why final SNDR still cannot be accepted

This planning model answers only how much known-band noise ideal sampling would produce if the circuit remained at this operating point and were linear and stationary. It preserves the native model's total noise spectrum at that operating point, but cannot track:

- Changes in conductance and device noise as sampling switches turn on/off.
- Capacitor charging/discharging, hold phases, and state memory across conversions.
- Noise, correlations, and nonlinear mixing during comparator regeneration and actual operating trajectories.
- Cross-correlation among nodes during switching, and reference/clock modulation.
- Contributions outside the measured spectrum, complete PVT, mismatch, and top-level post-layout simulation.

Thus both `adc_noise_qualified` and `full_chain_sndr_qualified` are `false`. The program does not calculate an apparently passing ADC SNDR number; absent physical evidence, the acceptance function forcibly refuses release.

The real next requirement is a time-domain or periodic-noise engine preserving current SKY130 **BSIM4v5** noise behavior and correlations, followed by multibias, multidevice, and clocked-RC qualification before connecting the real ADC. Only v8 was found in the installed VACASK BSIM4 OSDI; earlier checks show noise differences up to approximately 3.14 dB, which a common correction factor cannot remove.

This round found no ready-to-enable dependency with passing v5 equivalence, so it did not propose unverified software installation as a solution. Continued open-source engine/v5 model porting is a separate tool-development and multibias-equivalence task, not a single noise-switch change; new source dependencies, exact revisions, and licenses need separate review before download.

## 4. Files, verification, and reproduction

- [qualification.json](qualification.json): structured qualification and release-refusal reasons.
- [environment.json](environment.json): tools, PDK, binary fingerprints, and run constraints.
- [thermal_resistor.va](thermal_resistor.va): the original minimum OSDI control device created this round.
- [probe.py](probe.py): at most four processes per invocation, single-threaded by default, each limited to 180 seconds, without automatic retries of failed circuits.
- [test_hybrid.py](test_hybrid.py), [test_qualification.py](test_qualification.py): analytical integration, folding, seeds, statistical normalization, raw-evidence fingerprints, and negative acceptance tests.
- [xyce_capability.json](xyce_capability.json): local Xyce 7.10 identity/build capability record, without noise-circuit results.

This round adds **25 offline tests, all passing** (including 2 checking Xyce identity evidence). They qualify tool implementation and honest status assessment, not 25 passing chip-performance items.

Physical small cells execute in the fixed container; this round's four-run budget is exhausted. **After a new run budget is authorized**, `python3 /repo/v2/verification/noise_closure_20260911/probe.py` can be called again in the same environment, creating a new timestamped directory without overwriting old results. Compilation artifacts remain only in container `/tmp`; PDK parameters, models, rules, and licenses were not copied into the repository.

Offline recalculation without new simulations:

```sh
python3 v2/verification/noise_closure_20260911/analyze.py v2/verification/noise_closure_20260911/results/20260911T080040Z
python3 -m unittest discover -s v2/verification/noise_closure_20260911 -p 'test_*.py' -v
```

Passing tool/physical-capability checks cannot be reported as passing chip-noise metrics; passing a finite-band stationary planning model cannot be reported as completed noisy switched-ADC simulation.
