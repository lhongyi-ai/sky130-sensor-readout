#!/bin/bash
# The root agent owns the sole EDA slot. This script never changes the PDK.
set -euo pipefail
P1_CASE=${1:-}; P1_BUDGET=${2:-60}
case "$P1_CASE" in dn20u|dn5u|dn1u|d0|dp1u|dp5u|dp20u) ;; *) echo 'Usage: bash run_case.sh dn20u|dn5u|dn1u|d0|dp1u|dp5u|dp20u [budget_seconds]'; exit 64;; esac
case "$P1_BUDGET" in *[!0-9]*|'') exit 64;; esac
if [ "$P1_BUDGET" -lt 1 ]; then exit 64; fi
P1_ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
P1_OUT="$P1_ROOT/results/${P1_CASE}_$(date -u +%Y%m%dT%H%M%SZ)_$$"
mkdir -p "$P1_ROOT/results"
mkdir "$P1_OUT"
cp "$P1_ROOT/cases/$P1_CASE/input.scs" "$P1_OUT/input.scs"
cp "$P1_ROOT/manifest.json" "$P1_OUT/package_manifest.json"
printf '%s\n' "$P1_CASE" >"$P1_OUT/case.txt"
P1_SPECTRE=${P1_SPECTRE:-/opt/cadence/spectre/tools/bin/spectre}
cd "$P1_OUT"
sha256sum input.scs package_manifest.json >input_sha256.txt
env -u LD_LIBRARY_PATH /usr/bin/python3 "$P1_ROOT/verify_inputs.py" "$P1_ROOT"
env -u LD_LIBRARY_PATH /usr/bin/python3 "$P1_ROOT/limited_model_metadata.py" model_metadata_before.json
printf '%s\n' "$P1_SPECTRE -64 input.scs +log spectre.out -format psfascii" >command.txt
set +e
timeout "${P1_BUDGET}s" "$P1_SPECTRE" -64 input.scs +log spectre.out -format psfascii >driver.log 2>&1
P1_RC=$?
set -e
printf '%s\n' "$P1_RC" >exit_code.txt
env -u LD_LIBRARY_PATH /usr/bin/python3 "$P1_ROOT/limited_model_metadata.py" model_metadata_after.json
set +e
cmp -s model_metadata_before.json model_metadata_after.json
P1_METADATA_RC=$?
set -e
printf '%s\n' "$P1_METADATA_RC" >model_hash_comparison_exit.txt
printf '%s\n' "$P1_OUT"
if [ "$P1_RC" -ne 0 ]; then exit "$P1_RC"; fi
if [ "$P1_METADATA_RC" -ne 0 ]; then exit 65; fi
# A zero runner exit is completion of execution only. Analyze raw results separately.
