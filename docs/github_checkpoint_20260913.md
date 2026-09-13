# GitHub Engineering Checkpoint: 2026-09-13

This repository preserves completed engineering work and reviewable results. The complete chip has not passed qualification. Design targets, tool checks, behavioral-model results, transistor-level simulations, and school measurements remain distinguished according to their original reports.

## Included scope

- All previously committed original OTA files and Git history, based on commit `6e7f782fccecc0c2a047435744b26ffeb0db175f`.
- V2's original models, SPICE circuits, SAR RTL, tests, analysis scripts, configuration, documentation, layouts, and result summaries, retaining known failures and unfinished tasks.
- Cadence migration scripts, project-authored delivery packages, review programs, comparison tables, figures, and review reports. Start with [Cadence status](../cadence/project1/README.md) for the latest school results.
- The initial checkpoint copied 7,706 original project files, approximately 525.95 MiB uncompressed, plus publication notes and verification records. It prepended checkpoint navigation to the original homepage and appended exclusions to the root `.gitignore`, preserving their original content. The subsequent English edition translates documentation and display text and renames language-specific paths; see [English-edition notes](english_publication_20260913.md).

## Data retained locally

The [file inventory](github_checkpoint_manifest_20260913.json) records byte counts and SHA-256 hashes for included and local-only files. Its original checkpoint inventory covers 5,333 local-only files, approximately 2,585.98 MiB, including:

- New DAT/TSV/CSV/NPZ numeric data files larger than 1 MiB.
- Original school-return directories, complete return ZIPs, and environment metadata. Completed result reviews and summaries remain included.
- Locally generated digital-bridge binaries, compiler intermediates, and usage records.

Logs, RAW waveforms, caches, and other files already ignored by the original repository remain subject to its existing rules and are outside this inventory. These files have not been moved or deleted from the original project directory.

**This repository is not a backup of all raw simulation evidence.** Original measurement hashes remain provenance records. The English edition supplies published paths and hashes separately where translation changes bytes or filenames. Links to local-only files and evidence replay require the corresponding original project files. Cloning this repository alone is insufficient to run every test that depends on historical waveforms, school returns, or compiled binaries. Tests have not been changed to skip missing evidence or convert it into a passing result.

## Checks performed for the initial checkpoint

The [publication-copy verification record](github_checkpoint_validation_20260913.json) preserves command results and output:

- 23 behavioral-analysis tests and 21 behavioral-model tests passed.
- SAR digital RTL compilation and self-checking simulation passed; the actual check count is in the record. This does not establish analog ADC performance or physical timing qualification.
- 341 Python source files passed syntax parsing.
- 7,706 original files were checked by hash or by byte-for-byte validation of the intentional documentation additions.
- A limited scan of included files and delivery ZIP contents found no matches for common access-token and private-key formats.

The checkpoint operation prepared a publication copy without rerunning analog simulations or the complete historical evidence suite. Historical PASS/FAIL results retain their original scope. Importing simulator-generated tables produces whitespace diagnostics; their bytes are retained to preserve evidence integrity. Checks for the later English edition are recorded separately.

The model and RTL checks can be reproduced from the repository root with Python 3.12, NumPy, and Icarus Verilog/vvp:

```sh
PYTHONPATH=v2 python3 -m unittest discover -s v2/tests -p test_analysis.py -v
PYTHONPATH=v2 python3 -m unittest discover -s v2/tests -p test_model.py -v
python3 v2/tests/rtl/run.py
```

`v2/scripts/run_validation.py` includes additional historical-evidence tests outside the portable checks above; restore their required original files before running it. Configure the PDK, commercial tools, licenses, and local toolchains separately according to each subdirectory's documentation.
