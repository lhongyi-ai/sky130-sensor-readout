# MIM reference planes and RC ownership r3

Thirty-seven source/hash/numeric/scope review checks passed, while `physical_RC_ownership_qualified=false`. No model or original DSPF was changed.

The public model contains area/perimeter C, `rm3×lc/wc` and contact resistance divided by continuous `wc×lc/(0.17+0.25+0.140)^2`. It provides no integer cut count, contact coverage/location or port coordinates. Electrical series order does not determine a geometric reference plane. For4×8µm the model effective count is101.0862, while tested layouts have171 or19 actual cuts.

Magic PCell w/l use local x/y and allow contact-coverage variation. Its extraction distinguishes MIM-contact4.5Ω from ordinary via3=3.41Ω; neither value can simply replace the school's model without applicable provenance. Legal DRC/LVS contact variants need not lie inside one w/l-only model's characterized geometry range.

The actual controls show changed access resistance and a retained rotation-dependent1GHz ESR difference. Matching total C or DC access R does not ensure identical distributed impedance. Missing reference planes forbid arbitrary removal of internal R, plate R or perimeter C, and guessed scalar subtraction is not de-embedding.

Source versions, direction/contact counterexamples, actual-school input hashes and numerical comparisons are retained in `independent_audit.json` and adjacent records. Formal ADC PEX remains blocked independently of ADC functional progress.
