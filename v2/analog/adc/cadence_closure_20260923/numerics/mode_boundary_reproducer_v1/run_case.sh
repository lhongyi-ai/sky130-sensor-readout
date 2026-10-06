#!/bin/bash
# Invoked only by the root scheduler inside the existing configured school environment.
set -euo pipefail
P1_CASE=${1:-}; P1_PROFILE=${2:-}; P1_BUDGET=${3:-120}
case "$P1_CASE" in matched|static_gate|slow_10x|finite_1ohm) ;; *) echo 'case: matched|static_gate|slow_10x|finite_1ohm'; exit 64;; esac
case "$P1_PROFILE" in baseline|strict) ;; *) echo 'profile: baseline|strict'; exit 64;; esac
case "$P1_BUDGET" in *[!0-9]*|'') exit 64;; esac
P1_ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
P1_OUT="$P1_ROOT/results/${P1_CASE}_${P1_PROFILE}_$(date -u +%Y%m%dT%H%M%SZ)_$$"
mkdir -p "$P1_ROOT/results"
mkdir "$P1_OUT"
cp "$P1_ROOT/cases/$P1_CASE/$P1_PROFILE/input.scs" "$P1_OUT/input.scs"
cp "$P1_ROOT/manifest.json" "$P1_OUT/package_manifest.json"
printf '%s\n' "$P1_CASE" >"$P1_OUT/case.txt"
printf '%s\n' "$P1_PROFILE" >"$P1_OUT/profile.txt"
P1_SPECTRE=${P1_SPECTRE:-/opt/cadence/spectre/tools/bin/spectre}
cd "$P1_OUT"
sha256sum input.scs package_manifest.json >input_sha256.txt
printf '%s\n' "$P1_SPECTRE -64 input.scs +diagnose +log spectre.out -format psfascii" >command.txt
set +e
timeout "${P1_BUDGET}s" "$P1_SPECTRE" -64 input.scs +diagnose +log spectre.out -format psfascii >driver.log 2>&1
P1_RC=$?
set -e
printf '%s\n' "$P1_RC" >exit_code.txt
if [ -f input.raw/mode_boundary.tran.tran ]; then gzip -c input.raw/mode_boundary.tran.tran >trace.tran.gz; fi
printf '%s\n' "$P1_OUT"
exit "$P1_RC"
