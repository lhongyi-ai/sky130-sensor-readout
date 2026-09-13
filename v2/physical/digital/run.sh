#!/usr/bin/env bash
set -euo pipefail
# Run inside the prepared offline EDA container; no tool or PDK downloads.
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$TASK_ROOT"
librelane --manual-pdk --pdk-root /foss/pdks --pdk sky130A \
  --scl sky130_fd_sc_hd --jobs 2 --run-tag "${SAR_PHYSICAL_RUN_TAG:-final}" \
  --condensed --log-level ERROR v2/physical/digital/config.json
