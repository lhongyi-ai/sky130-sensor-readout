# English publication and privacy scope — October 6, 2026

This edition publishes the latest project-owned design sources, analysis programs, result summaries and engineering reports. The initial English checkpoint contains engineering evidence through September 24, 2026. Translation, anonymization and package checks are publication work. A subsequent complete-load first-edge control was actually run in school Spectre on October 6 and is published separately; it does not qualify the original RTL or complete ADC.

## English edition

The current publication uses English filenames, documentation, code comments and generated report text. The existing English baseline is retained. An offline translator supplied initial drafts, followed by direct technical editing of all 83 new English reports. The English technical editions condense narrative while preserving result meaning, failure states and links to detailed machine-readable evidence. The main progress report, actual ADC results and stability-method contract were checked directly against the original evidence. Code prose/path changes were checked to preserve the non-text Python AST. Numeric results, failure states and design requirements remain unchanged.

The original local project and school evidence are preserved separately. This edition does not replace their historical input hashes. The publication inventory records original source hashes and separate hashes of published bytes. An original source-path digest identifies renamed files without publishing private or non-English source names. Historical manifests still describe their original runs; they are not promises that translated report bytes have the same hash.

## Excluded material

This publication excludes school PDK and model source files, installed tool manuals, proprietary verification decks and extraction technology, raw school report archives, waveform databases, credentials, license keys and school account or host details. Project-owned supplemental rules are explicitly experimental and do not represent foundry signoff coverage.

School paths and license locators in instructions and launchers use generic placeholders. A real installation must supply its own authorized paths and environment. The publication does not reproduce that installation. Some report links intentionally identify local-only evidence that is not distributed; hashes and summary measurements remain available for review.

Large raw records, simulator scratch, compiled artifacts and local translation preparation are excluded. Current-tree publication checks do not rewrite earlier Git history. They do not certify or remove information in historical commits.

## Delivery archives

Retained delivery ZIPs are English publication editions. Privacy substitutions change their bytes, so ZIP sidecars, operational payload manifests and base/patch bindings have been updated together. A fresh English 1.0.4 base followed by p1, p2 and p3 was checked locally, including repeat application of every patch. Use matching editions together; do not assume that an English-edition patch binds to a previously installed package with different bytes.

These package checks validate packaging and installation logic. The edited packages have **not** been rerun in the school's licensed Cadence environment. Published historical simulation results retain their original provenance and do not acquire a new simulation PASS from translation or packaging.

## Current qualification limits

The original RTL has produced two frames with the actual ADC and completed the reset-abort protocol checks. Full numerical convergence remains unqualified. A complete short-window comparison still exceeds 9.765625 µV, and subsequent finer runs did not complete the required interval. Equal output codes and low error at selected decision instants do not waive that full-domain requirement.

MIM geometric and connectivity controls have advanced, but CAPM coupling references, internal/external RC reference planes and resistance-temperature provenance remain unresolved. `formal_ADC_PEX_allowed=false`. Public-tool CDAC results are kept separate from school extraction and from actual ADC full-code testing.

See [current progress](progress_20261006.md), [publication inventory](publication_inventory_20261006.json) and [local validation record](publication_validation_20261006.json). No fabrication, silicon measurement, complete-core qualification or production yield is claimed.

## Subsequent October 6 diagnostic

The complete native boundary-control sources and summary were checked for English-only content and private environment strings before publication. Twelve focused local checks passed; two serial school Spectre runs completed. The strict run missed the sample edge and is explicitly failed. Raw school runs remain local. The earlier publication inventory and validation records describe the initial checkpoint; this additional diagnostic is bound by its own input/reference/raw hashes in review.json.
