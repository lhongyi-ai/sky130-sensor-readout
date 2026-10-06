#!/bin/bash
# Run once inside a NEW prepared profile directory and school Spectre21 environment.
# Diagnostic execution only: no completed ADC conversion or protocol PASS expected.
set -uo pipefail
P2_LIMIT="${1:-180}"
case "$P2_LIMIT" in ''|*[!0-9]*) exit 2;; esac
if [ "$P2_LIMIT" -lt 1 ] || [ "$P2_LIMIT" -gt 300 ]; then exit 2; fi
if [ -e driver.log ] || [ -e simulator_exit_code.txt ] || [ -e xcelium.d ]; then
 printf '%s\n' 'Existing attempt found. Preserve it; use a new directory.'; exit 2
fi
sha256sum -c SHA256SUMS > input_integrity.log 2>&1 || exit 3
command -v xrun > actual_xrun_path.txt || exit 3
xrun -version > tool_version.txt 2>&1
printf '%s\n' 'xrun -64bit -ams -top p2_ams_reset1 -spectre_args "-format psfascii" -incdir /opt/cadence/XCELIUM2209/tools.lnx86/spectre/etc/ahdl sar_controller.v p1_interfaces.vams p2_ams_reset1.vams p2_sequence.sv amsdControl.scs -l xrun.log' > command.txt
timeout --signal=TERM --kill-after=10s "${P2_LIMIT}s" xrun -64bit -ams -top p2_ams_reset1 -spectre_args "-format psfascii" \
 -incdir /opt/cadence/XCELIUM2209/tools.lnx86/spectre/etc/ahdl \
 sar_controller.v p1_interfaces.vams p2_ams_reset1.vams p2_sequence.sv amsdControl.scs -l xrun.log > driver.log 2>&1
P2_RC=$?
printf '%s\n' "$P2_RC" > simulator_exit_code.txt
printf '%s\n' 'SHORT_DIAGNOSTIC_ONLY; ZERO_COMPLETED_FRAMES_EXPECTED; ADC_QUALIFICATION_NOT_EVALUATED' > diagnostic_scope.txt
P2_REVIEW_RC="$P2_RC"
if [ "$P2_RC" -eq 0 ] && grep -q 'P2_FAIL' driver.log; then P2_REVIEW_RC=2; fi
printf '%s\n' "$P2_REVIEW_RC" > diagnostic_execution_exit_code.txt
# Zero means process completion only. Actual points/parameters/warnings require review.
exit "$P2_REVIEW_RC"
