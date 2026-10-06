# MIM r3 provenance and boundary counterexamples

Actual new school layouts, PVS, Quantus and Spectre controls add evidence without qualifying formal ADC PEX. Installed technology hashes match r2; r1/r2 and historical results are unchanged.

School device models also use30°C; exported QRC reference is25°C. The latter is an effective tool reference, not an established manufacturing measurement temperature. Same-temperature sheet/via differences approximately1.7438%/1.2234% remain unexplained. Public unmerged ITF material does not prove the school's technology provenance.

Four4×8 µm controls have full171 contacts, rigid90° rotation, left19 contacts or right19 contacts. Project DRC/LVS passed; wrong-axis and swapped-port sources were rejected. PLUS access R was0.074110/0.074110/0.224000/0.243282 Ω, MINUS0.052875 Ω. Model C remains67.94225 fF and effective contact count101.0862 regardless of actual cut count, exposing unresolved coverage/ownership.

Eight QRC extractions and six Spectre AC runs completed. Spectre had zero errors/warnings. Rigid rotation preserved access DC R and nearly total C but changed distributed capacitor placement and1GHz ESR approximately0.23488743→0.23364656 Ω, about−0.5283%. Refinement/explicit-via controls retained approximately−0.52423%/−0.55735% differences. These are ESR discrepancies, not ADC conversion errors; settings are not rigorous bounds or selectable physical truths.

Physical gates remain: reference-temperature/version provenance; model local axes, contact coverage and port reference planes; credible CAPM stack or supported package and independent coupling reference; then numerical rotation/multiport/array validation. `formal_ADC_PEX_allowed=false`. Same-network agreement and zero simulator warnings do not remove extraction warnings or missing physical data.
