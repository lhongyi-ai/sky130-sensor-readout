#!/bin/bash
# Run from a NEW, isolated prepared folder, inside the already configured school container.
# No environment setup, GUI access, library modification, or parallel jobs here.
set -uo pipefail
P2_LIMIT="${1:-300}"
case "$P2_LIMIT" in ''|*[!0-9]*) printf '%s\n' 'Timeout must be positive integer seconds'; exit 2;; esac
if [ "$P2_LIMIT" -lt 1 ] || [ "$P2_LIMIT" -gt 1800 ]; then exit 2; fi
if [ -e driver.log ] || [ -e simulator_exit_code.txt ] || [ -e xcelium.d ]; then
 printf '%s\n' 'Existing attempt found; preserve it and prepare a new directory.'; exit 2
fi
command -v xrun > actual_xrun_path.txt || exit 3
xrun -version > tool_version.txt 2>&1
sha256sum sar_controller.v p1_interfaces.vams p2_ams_reset1.vams p2_sequence.sv profile.vh reset1_native_bound.scs amsdControl.scs > run_input_sha256.txt
printf '%s\n' 'xrun -64bit -ams -top p2_ams_reset1 -spectre_args "-format psfascii" -incdir /opt/cadence/XCELIUM2209/tools.lnx86/spectre/etc/ahdl sar_controller.v p1_interfaces.vams p2_ams_reset1.vams p2_sequence.sv amsdControl.scs -l xrun.log' > command.txt
timeout --signal=TERM --kill-after=10s "${P2_LIMIT}s" xrun -64bit -ams -top p2_ams_reset1 -spectre_args "-format psfascii" \
 -incdir /opt/cadence/XCELIUM2209/tools.lnx86/spectre/etc/ahdl \
 sar_controller.v p1_interfaces.vams p2_ams_reset1.vams p2_sequence.sv amsdControl.scs -l xrun.log > driver.log 2>&1
P2_RC=$?
printf '%s\n' "$P2_RC" > simulator_exit_code.txt
# IEEE1364-compatible $finish may return zero on a functional failure.
# Keep the real simulator exit separate from this preliminary protocol status.
P2_QUALIFY_RC="$P2_RC"
if [ "$P2_RC" -eq 0 ]; then
 if ! grep -q 'P2_HANDSHAKE_PASS frames=' driver.log; then P2_QUALIFY_RC=2; fi
 if grep -q 'P2_FAIL' driver.log; then P2_QUALIFY_RC=2; fi
fi
printf '%s\n' "$P2_QUALIFY_RC" > qualification_exit_code.txt
# Full evidence analysis is independent: marker success never means ADC accuracy PASS.
exit "$P2_QUALIFY_RC"
