# Native ADC and original RTL verification

This independent revision preserves the original design, RTL, stimuli and failed runs. The reset1 ADC has 693 devices and 27 ports; the native phase circuit adds 48 devices, for 741 total. All comparison decisions use the actual comparator, without prerecorded answers or an ideal comparator substitute.

The complete two-frame baseline produced codes 5/4090, all 24 real comparator decisions and the additional reset-abort check. Numerical convergence is still not qualified. The strict run timed out before the complete source-defined protocol ended. Equal codes and small errors at decision instants do not waive the original full-domain requirement on TP−TN, RP, RN and VCM: 0.05 LSB = 9.765625 µV.

Controlled runs localize precision sensitivity around source/drain mode reversal and actual phase/load switching, but have not established a model defect or supported repair. See [detailed results](RESULTS.md), [numerical diagnosis](numerics/README.md) and `STATUS.json` for actual states; prepared packages do not imply execution.

Raw runs, school configuration, PDK and large waveforms remain local. Formal MIM/array PEX is also incomplete: CAPM physical coupling, internal/external RC boundaries and resistance provenance remain unresolved, so `formal_ADC_PEX_allowed=false`. Numerical qualification precedes 12-frame, full-code, reference-drive, device-noise, PVT and statistical campaigns.
