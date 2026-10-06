# Newer-tool cross-check

The first-acquisition actual ADC probe still reported SPECTRE-16780 on the same CONV PFET near 4.0632 µs with Spectre25.1.0.156.isr2/Xcelium25.03-s006. The older combination was Spectre21.1.0.132/Xcelium22.09-s013. Seven circuit/RTL/stimulus/configuration input hashes matched, but both tools changed, so differences cannot be assigned only to Spectre.

The newer run had 26 warnings: 22 VACOMP-2506 portability messages, one SFE-3453 save rejection, one SPECTRE-8282 skipped save, one AHDLLINT-8007 time-step event and one SPECTRE-16780 LTE relaxation. It saved 75 common voltage channels instead of 76; int_b was missing. A save rejection does not mean the body network vanished.

Both runs had 4950 accepted steps, 116 LTE rejections and four Newton rejections. The independent comparator had fewer printed LTE warnings but still reached Newton recovery and a bsource warning. Neither warning counts nor functional checks establish convergence. Preserve the same original threshold and resolve actual observability before comparing internal waveforms.

Evidence: `version25_probe_review.json`; no PDK or circuit changed by this read-only review.
