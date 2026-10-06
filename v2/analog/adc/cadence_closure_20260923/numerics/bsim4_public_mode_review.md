# Public BSIM4 mode-reversal review

Status: PUBLIC_MODEL_LIMITATION_RELEVANT / LOCAL_ROOT_CAUSE_NOT_PROVEN / SUPPORTED_LOCAL_FIX_NOT_FOUND. The review used Berkeley reference source/manuals, original model-team material and official Cadence discussions. It did not run EDA, change models or contact support.

Historical BSIM3/4 source/drain symmetry and charge/current derivative limitations near VDS=0 support investigation of this boundary, but no identified supported fix matches the school pfet_01v8/rbodymod=1/Spectre21-or-25 internal-body warning. Source literals include version=4.5, five 50 Ω body resistances and gbmin=1e−12; they are not proof of the proprietary implementation's execution path.

The official BSIM450 ZIP contains loose source files labeled 4.4.0. The actual 4.5.0 references in this review came from its nested BSIM450.tar.Z with the 2005-07-29 header. Berkeley reference implementation is not Cadence source. Switching simulator versions is not the same as upgrading the PDK's model version.

Official source: [Berkeley BSIM4](https://bsim.berkeley.edu/models/bsim4/). Detailed source locations, document hashes and distinctions remain in adjacent review metadata. Raw Q aliases and unresolved exported-option sentinels require clarification; general forum suggestions do not authorize model replacement, disabled body resistance or artificial cmin. Complete ADC convergence remains failed/incomplete.
