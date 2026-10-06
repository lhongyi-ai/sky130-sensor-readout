# Spectre noise-method controls

Six actual school pilot runs exercised ideal RC noise, MIM AC value and RC/PDK-switch transient noise on/off pairs. This is a method/unit/statistics control, not ADC SNDR, mismatch or M2 qualification. All randomness comes from Spectre device noise.

For27°C, R=1 kΩ and C=141.8127 pF, `S_R=4kTR=1.65760719e−17 V²/Hz`, tau=141.8127 ns, fc=1.12229 MHz and integrated variance `kT/C=2.92217691e−11 V²`. Single-ended/independent differential RMS are5.40572/7.64484µV. ASD must be squared before frequency integration. A fixed-state noise analysis cannot replace switched dynamic noise.

The TG proxy uses real LVT switches/dummies,350Ω sources and a lumped4×4µm MIM with m=4096. It is not the actual distributed bottom-plate ADC. Actual MIM AC was141.8127398pF. Pilot records retain64 samples after16 discarded cycles, seed11,60MHz white-noise setting. Direct solved strobes are pre_open=j×10µs+3.499µs, post_open=+3.620µs and late_hold=+10.900µs. Identical noise-off twins separate deterministic injection from sampled random variance.

| Control | Phase | Differential RMS, µV |
| --- | --- | ---: |
| RC | pre_open/post_open/late_hold | 7.287 / 6.668 / 6.390 |
| TG | pre_open/post_open/late_hold | 7.463 / 7.544 / 7.542 |

RC PSD maximum relative error was2.34e−5; integrated variance2.923706e−11V² versus same-band analytic2.922154e−11V². TG deterministic turn-off injection was approximately+0.811µV. TG retained a real SPECTRE-16780 at313.5µs, so numerical noise qualification remains failed. Small-sample RC variance/correlation also warrants further review. Parser singular-warning and missing-file failures are retained with separate corrected reviews.

Do not launch the prepared1024-point/three-seed/bandwidth matrix before numeric eligibility and resource review. Report autocorrelation, effective sample counts and qualified variance intervals; correlated samples are not independent yield evidence. Runtime estimates are projections. Inputs, actual statuses and statistics remain in `pilot_report.json`, `prepared/` and analysis scripts. No synthetic random waveforms or changed acceptance targets were used.
