# School AMS interface qualification

Actual Xcelium/Spectre RC electrical↔digital interface tests passed eight checks with zero Spectre errors/warnings. Shared E2L/L2E modules compiled and ran. Original RTL regression also passed. These are environment/interface controls, not ADC performance.

The actual-ADC two-frame harness compiled/elaborated and began simulation, then timed out at the first acquisition transition after300seconds without a complete frame. That failed attempt remains separate from later reset1/full-ADC work.

Signal flow is actual Q/QB→E2L→original SAR RTL→L2E→real trial switches and phases→actual CDAC/comparator. The public RC smoke inputs and `environment_result.json` preserve the qualified interface evidence. Raw school environment/log/waveform/configuration stays local.

Run only in the matching configured tool environment; native subcircuit portmap/config binding and actual interface disciplines require verification. An installed executable, successful elaboration or RC-control PASS does not qualify actual ADC convergence, noise, full code, PVT or PEX.
