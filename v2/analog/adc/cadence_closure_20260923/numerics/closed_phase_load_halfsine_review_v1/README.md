# Half-sine reduced-circuit stimulus control

Only the command edge shape changed to half-sine with transitionreference=100, retaining its 4.0625 µs start, 1 ns duration and 0/1.8 V endpoints. The same 654-device reduced native circuit and 104 CONV gate loads were used. This is a verified stimulus change, not original-stimulus equivalence.

Both runs completed 0–4.1 µs. Saved command samples match `0.9[1−cos(πu)]` within 3.13 pV; the previous skipped-edge gap disappeared. Strict retained four SPECTRE-16780 warnings on other actual body nodes. There were no 17087 breakpoint skips or 16266 LTE ignores in this control.

The complete TP−TN difference was 1.127887 mV, CONV 304.202 µV, RP 3.2727 nV and RN 2.4411 nV. The TP−TN peak remains above 9.765625 µV. Changes in midpoint voltage, threshold timing and maximum slew accompany the smoother shape, so the effect cannot be attributed only to derivative continuity.

Source interpolation differences are reported separately and do not erase the delayed TP−TN peak. There is no original full-ADC/RTL qualification. Exact log contexts, input hashes and neighbors remain in `review.json` and `provenance_and_peak_context.json`.
