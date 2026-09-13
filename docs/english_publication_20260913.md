# English Publication Edition: 2026-09-13

The current repository checkout is the English edition of the completed-work checkpoint. Documentation, explanatory comments, generated report prose, diagram labels, filenames, and delivery-archive instructions are translated into English. Previous Git commits retain their original historical content.

## Translation and engineering scope

The translation preserves technical conditions, numerical values, code behavior, qualification scope, known failures, and unfinished work. It does not constitute a new analog simulation, school execution, or chip qualification. Raw numerical results, circuit netlists, RTL, and existing raster/PDF results are checked separately for byte preservation.

Human-readable paths are renamed to English, with references in source code, documentation, and metadata updated consistently. Historical evidence hashes remain records of the original source bytes. They must not be interpreted as hashes of newly translated documentation or display strings. The English-edition verification record identifies changed publication files using their original and current hashes.

The original project and school-return packages remain in the original local project directory. This publication copy still omits the large waveforms, original school-return folders, and build products listed in the [checkpoint inventory](github_checkpoint_manifest_20260913.json).

## English delivery archives

All 12 retained delivery ZIPs contain English instructions and filenames. Their operational manifests, checksum sidecars, and runtime-patch base-package bindings are refreshed. Each archive includes an `ENGLISH_EDITION.md` note with the original archive hash.

These archives are translated distributions of the same circuit versions. **They have not been executed at the school.** Existing school execution evidence refers to the original package bytes. The translated runtime patches require their matching English base package; they are not intended for an existing installation of the original package. The original local school packages remain available for that installation.

Local validation extracts the English base package, applies the three runtime patches in sequence, and checks repeat installation. It also verifies archive file hashes. These checks establish local package consistency, not commercial-tool or school-environment compatibility.

## Verification

The [English-edition verification record](english_publication_validation_20260913.json) records the final language scan, archive checks, source checks, and model/RTL test results.

The language check examines tracked UTF-8 text, decoded JSON, archive member names and text, and compressed numeric metadata for remaining Chinese characters. The four existing PDFs were checked through extracted text. All 49 existing PNGs were checked with local macOS text recognition using English and Simplified Chinese recognition settings; no Chinese labels were found. OCR is a text-detection check rather than a proof of every pixel's semantics. Both translated SVGs are rendered and visually reviewed for label fit.

Previous checkpoint and circuit-validation records remain historical records. Source fingerprints inside those records may refer to the pretranslation source. Restoring omitted raw data and the matching source version remains necessary for full historical evidence replay; missing evidence has not been converted into a passing result.
