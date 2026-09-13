# Legacy OTA Remaining 32 Items: Corresponding Local Reruns

The 32 corresponding local ngspice tests are complete, plus two differential references. Complete reports:

- [Reproduction report and curves](reviews/20260913T062428272833Z/reproduction_report.md)
- [Per-item status of all 32 tests](reviews/20260913T062428272833Z/jobs32.csv)
- [Machine-readable results](reviews/20260913T062428272833Z/review.json)
- [Raw-data coverage and comparison of 13 MOS operating points](evidence_check_20260913T061726614895Z.json)

This is not a new school Cadence run. Dimensions, diffusion geometries, and test connections actually exported by the school are retained to form a comparison baseline in local open-source models. The 32 school extra items still require actual execution and returned data.

Results contain real performance failures: PSRR± approximately 36.33/36.10 dB; valid ICMR on a 0.1 V grid is 0.8–1.2 V; extended-load phase margin at 10/20 pF is approximately 53.77°/40.55°. Noise is 401.15 nV/√Hz @1 kHz and 52.30 µV RMS (10 Hz–1 MHz), without a legacy OTA hard threshold, and all model warnings are retained.

All valid runs are in `runs/20260913T061726614895Z/`; the same-bias differential reference is in `rejection_reference/20260913T061918108509Z/`. The first smoke run's false PMOS-sign-adaptation failure is separately retained. The original legacy OTA, school library, and historical results were not changed.

`run_campaign.py` / `run_rejection_reference.py` run in `/repo` in the existing local EDA container; `build_report.py` / `check_evidence.py` analyze in local Python + NumPy + Matplotlib. **These are not school Python 3.6.8 upload packages.** Reruns create new timestamped directories; old results can be reviewed against source snapshots and hashes.
