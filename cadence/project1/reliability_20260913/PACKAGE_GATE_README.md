# Release gate for new upload packages (2026-09-13)

This directory adds `release_gate.py` to reduce corrupt-package, mixed-version, dependency, and compatibility incidents on school Linux. **No new frontend upload package has been built or released: the new frontend is not yet frozen.** The school environment was not operated, and existing `regression*.log/json` files in this directory were not changed.

Only 13 synthetic small-package tests ran in this round: an otherwise complete local package remains blocked without an on-site canary; corrupt ZIPs, multiple roots, omitted file listings, incorrect SHA values, mixed versions, CRLF, internal-path spaces, newer Python syntax/non-3.6 standard-library dependencies, and old/mock canaries were all rejected. See `release_gate_tests.log`. These are **local tool tests, not school pass records**.

## Usage

```sh
python3 release_gate.py '/path with spaces/new_package.zip' --output preflight.json
python3 release_gate.py '/path with spaces/new_package.zip' --canary school_evidence/canary.json --output release_check.json
```

Without a qualifying on-site canary, the exit code is **2** and `batch_release_allowed=false`. The first command may produce `local_preflight_pass=true` but still does not release batch execution; repeated new-patch uploads are unnecessary for this state. The gate only reads the ZIP: it neither extracts nor installs it and starts no simulation.

The ZIP's external storage path may contain spaces when properly quoted. To eliminate uncertainty in school-script path propagation, internal directory and file names in new release ZIPs must not contain whitespace.

## Fixed contract for new packages

The ZIP has exactly one top-level directory; absolute paths, `..`, backslashes, symbolic links, duplicate paths, and noncanonical paths are forbidden. This root contains `release_gate_manifest.json` in this format:

```json
{
  "release_id": "frontend_frozen_version_here",
  "version": "frozen_version_here",
  "root_dir": "frontend_frozen_version_here",
  "files": {
    "run.py": "SHA-256 of the complete file",
    "start.sh": "SHA-256 of the complete file"
  }
}
```

`files` must cover every nondirectory file in the ZIP individually, except the manifest itself. The outer SHA of the entire ZIP constrains the manifest, avoiding an impossible self-hash requirement. If `package_manifest.json` exists, its version must match the new-package manifest; historical `patch_backups` must not be mixed into the package. The checker also reads the entire ZIP to verify CRC and every file SHA.

All packaged `.py` files are checked as **school execution files** for Python 3.6 syntax and standard-library imports; local-only build/analysis scripts should remain local. Dependencies/syntax such as `numpy`, `dataclasses`, future annotations, and the walrus operator are forbidden. Known newer standard-library APIs and dynamic loading/execution require explicit handling and cannot be released solely by static import checks. `.py/.sh/.il/.ocn` files must not contain CRLF, isolated CR, or a UTF-8 BOM.

Static rules are conservative checks and cannot establish compatibility of all dynamic standard-library APIs, CDF callbacks, SKILL functions, or OCEAN signal exports; that is why an actual school canary is mandatory. The checker itself uses Python 3.6 syntax and standard libraries; Python 3.6 syntax parsing was performed locally this round, **without claiming actual execution in Python 3.6.8**.

## Binary bridges and school architecture

If a new package includes `.so`, version-suffixed `.so.N`, or any ELF file, the manifest must add `school_target_machine`, currently supporting `x86_64` or `aarch64`. The checker reads ELF magic, class, endianness, version, and e_machine: x86_64 requires ELF64/little/e_machine=62; aarch64 requires ELF64/little/e_machine=183. An undeclared target, architecture mismatch, or local ARM bridge inserted directly into an x86_64 school package is forbidden; Mach-O (including common universal/fat variants) and non-ELF `.so/.dylib` files are rejected. Pure Python/SKILL frontend packages without native files do not require these fields.

An actual school canary containing native files must also record `environment.machine`, exactly matching the manifest target, and add `steps.native_load`. This step follows the same V1 completion-marker protocol, with a `modules` array listing the relative path of every packaged native file and logs retaining actual load results. For example: `modules: ["cosim_controller_fixed.so"]`. Failed loading must not write a completion marker.

This round adds two **synthetic ELF-header** tests: ARM ELF addressed to x86_64 is rejected; correct x86_64 ELF metadata can pass only local header checks and remains blocked without a school canary. A correct ELF header does not establish compatibility of linked libraries, glibc/ABI, module loading, simulator interfaces, or continuous-conversion functionality; the actual school entry must truly load modules and run the corresponding minimum closed loop. No false school evidence was created and no local bridge was released to the school.

## Minimum school-canary evidence for the same package

Run one minimal canary serially from the formal package on school **Linux / Python 3.6.8 / IC6.1.8 / Spectre 21.x**, covering Python compilation, native-cell creation or reading, one Spectre simulation, and result export. Preserve complete logs and exit statuses for every step; have the actual execution entry write `canary.json`, without manually entering PASS locally:

```json
{
  "package_zip_sha256": "Complete SHA-256 of the ZIP actually executed at the school",
  "release_id": "Exactly matches the new package",
  "execution_kind": "ACTUAL_SCHOOL_CADENCE",
  "mock": false,
  "environment": {
    "platform": "Linux",
    "python": "3.6.8",
    "virtuoso": "Actual IC6.1.8 version output",
    "spectre": "Actual 21.1 version output"
  },
  "completed": true,
  "exit_code": 0,
  "steps": {
    "python_compile": {"completed": true, "exit_code": 0, "log": "python.log"},
    "native_create_or_open": {"completed": true, "exit_code": 0, "log": "native.log"},
    "spectre_canary": {"completed": true, "exit_code": 0, "log": "spectre.log"},
    "result_export": {"completed": true, "exit_code": 0, "log": "export.log", "outputs": ["result.csv"]}
  },
  "evidence": {
    "python.log": "SHA-256",
    "native.log": "SHA-256",
    "spectre.log": "SHA-256",
    "export.log": "SHA-256",
    "result.csv": "SHA-256"
  }
}
```

On-site exit code 0 and `completed=true` are **insufficient to pass**: the checker also reads every step's original log, rejecting known fatal markers such as `*Error*`, `ERROR (SPECTRE-...)`, `FATAL`, `no such vector`, undefined functions, CDF initialization failures, missing/failed exports, and Python traceback. `result_export` must also list actual nonempty export files that pass SHA verification.

Only after the corresponding subprocess completes, output-content checks pass, and exported files exist must the on-site execution entry write **exactly one standalone complete line** in that step's log:

```text
P1_CANARY_STEP_V1 COMPLETE <step_name> <64-character-SHA256-of-the-same-ZIP> <same-release_id>
```

`step_name` is respectively `python_compile`, `native_create_or_open`, `spectre_canary`, or `result_export`. Completion markers must not be prewritten, inferred from JSON completed fields, or appended after errors to override failure; logs containing any listed error are rejected even when a marker exists. Old canaries or canaries missing this V1 marker are not reused. **No new school entry implementing this protocol has been generated in this round**, so the new package remains unreleased.

Synthetic negative tests specifically cover “same package, exit 0, correct hashes, all markers present, but errors in original logs” and “same package, exit 0, missing completion marker.” Incorrect canary / steps / evidence / environment types are normalized into release-blocking results rather than allowing an exception exit to masquerade as a valid report. Protocol and hashes still check only evidence consistency, not machine origin; manual original-log review must be retained.

All evidence files must be in the directory containing `canary.json` or its subdirectories, actually exist, and match their hashes. Replacing the ZIP, changing version, or modifying logs immediately invalidates the old canary. The checker verifies binding and declaration consistency; school origin and circuit correctness still require original-log review. Hashes alone cannot establish which machine produced a log.

Past issues include Cadence library paths contaminating system Python, CDF initialization/callback differences, unavailable school SKILL functions, PCell-clamped device widths, and incompatible result-export names. These require a minimal on-site run to expose. `BATCH_RELEASE_ALLOWED` only indicates this package completed the delivery prerequisites above; it does not establish circuit performance, noise/PVT, or layout signoff.

Reproduce local false-pass prevention tests:

```sh
python3 test_release_gate.py
```
