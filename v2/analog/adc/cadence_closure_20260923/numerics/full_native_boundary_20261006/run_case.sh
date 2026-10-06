#!/bin/bash
set -euo pipefail
P1_PROFILE=${1:-}; P1_BUDGET=${2:-180}
case "$P1_PROFILE" in baseline|strict) ;; *) exit 64;; esac
case "$P1_BUDGET" in *[!0-9]*|'') exit 64;; esac
P1_ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
P1_OUT="$P1_ROOT/results/${P1_PROFILE}_$(date -u +%Y%m%dT%H%M%SZ)_$$"
mkdir -p "$P1_ROOT/results"
mkdir "$P1_OUT"
cp "$P1_ROOT/input_${P1_PROFILE}.scs" "$P1_OUT/input.scs"
cp "$P1_ROOT/native_full.scs" "$P1_OUT/native_full.scs"
cp "$P1_ROOT/manifest.json" "$P1_OUT/package_manifest.json"
printf '%s\n' "$P1_PROFILE" >"$P1_OUT/profile.txt"
cd "$P1_OUT"
sha256sum input.scs native_full.scs package_manifest.json >input_sha256.txt
spectre -W >tool_version.txt 2>&1
set +e
timeout "${P1_BUDGET}s" spectre -64 input.scs +diagnose +log spectre.out -format psfascii >driver.log 2>&1
P1_RC=$?
set -e
printf '%s\n' "$P1_RC" >exit_code.txt
shopt -s nullglob
P1_TRACES=(input.raw/full_boundary*.tran)
if [ "${#P1_TRACES[@]}" -eq 1 ]; then gzip -c "${P1_TRACES[0]}" >trace.tran.gz; fi
printf '%s\n' "$P1_OUT"
exit "$P1_RC"
