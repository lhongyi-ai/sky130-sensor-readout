# reset1 ADC and original RTL AMS entry

The current v4 two-frame pair combines the 693-device native reset1 ADC, 48-device phase circuit and byte-preserved original sar_controller RTL. RST_N is the ADC's 27th port and receives the same reset as the RTL through L2E. Only explicit subcircuit boundaries wrap the audited native bodies. No model, ideal comparison decision, leakage, IC or nodeset is added.

Conditions: TT, 27°C, VDD=1.8 V, VCM=0.9 V, 350 Ω per input, references 1.1/0.7 V through 1 Ω and 10 nF each. The school 4×4 µm MIM array has approximately 141.8 pF per side; old 3×3 µm dynamic results do not apply.

v1 requested tolerances that were inadvertently ten times tighter than the historical profile. v2 restored the requests and selected saves but failed school Verilog compilation at `$fatal`. v3 replaced those calls with explicit failure/finish markers while preserving RTL and stimuli. v4 changes only the error-reference method to sigglobal and expands diagnostic print limits. Every earlier failure is retained.

Baseline requests reltol=1e−5, Vabs=10 nV, Iabs=100 fA, maxstep=2 ns; strict requests 1e−6, 1 nV, 10 fA and 1 ns. Conservative mode changes effective reltol; verify actual settings in logs. Current actual outcomes are in [RESULTS](../RESULTS.md).

The 12-frame v3 package is prepared historical input, not authorized qualification after a failed numerical gate. A qualified method requires a new matching package. Each run must preserve actual codes, all decisions, busy/data_valid/data_gain/reset behavior, native hashes and full raw-domain comparisons. Neither compilation nor simulator exit 0 alone is ADC PASS.
