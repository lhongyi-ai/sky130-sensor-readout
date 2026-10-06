# Actual ADC/phase migration into native Cadence

The frozen actual ADC and original SAR RTL were mapped into independent school variants, preserving all old designs/results. Initial expansion contained617 MOS,17 process resistors and30 parameterized MIM instances; native resistor segmentation and reset changes have separately audited counts.

The two CDACs each represent4096 physical units through binary weights1…2048 plus dummy. Comparator and preamplifier capacitances are separate. Sample input goes to real bottom-plate acquisition switches, TOP/TOPB clamp the common plates to VCM, and actual preamplifier/StrongARM/holding NAND produce Q/QB. No ideal comparator or prerecorded decisions are used.

The original RTL maps actual Q to comparator_bit, trial_code to real bottom switches, sample_en to SAMPLE_CMD and comparator_evaluate to EVAL. data_gain belongs to the output code; gain remains latched for the conversion. Source comments do not override actual LVT/dummy device calls.

Local mapping arithmetic PASS is not native export or performance PASS. The later reset1 version has693 devices/27 ports and is reviewed in `reset1/`; complete ADC/RTL outcomes are in `../../../analog/adc/cadence_closure_20260923/RESULTS.md` from the physical workstream's root. Consult the repository progress page for correct navigation. Numerical and formal PEX qualification remain incomplete.
