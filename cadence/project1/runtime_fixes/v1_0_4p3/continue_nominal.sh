#!/usr/bin/env bash
# User-triggered sequence; first failure stops later tests and collects evidence.
set -euo pipefail
p1_op_fix_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
p1_op_launcher="${P1_OP_LAUNCHER:-$HOME/cadence_skywater/p1_school_run_v1.sh}"
p1_op_collect_ready=0
if [[ ! -f "$p1_op_launcher" ]]; then
  echo "Missing existing school launcher: $p1_op_launcher" >&2
  exit 1
fi
p1_op_finish() {
  p1_op_code=$?
  trap - EXIT
  if [[ "$p1_op_collect_ready" == 1 ]]; then
    if ! bash "$p1_op_launcher" collect; then
      echo "Report collection failed; preserve terminal output." >&2
      if [[ "$p1_op_code" == 0 ]]; then p1_op_code=1; fi
    fi
  fi
  exit "$p1_op_code"
}
trap p1_op_finish EXIT
bash "$p1_op_fix_dir/apply.sh"
p1_op_collect_ready=1
bash "$p1_op_launcher" recheck-passives
bash "$p1_op_launcher" resume-export --job P01_op --attempt 20260913T013236Z_ce589195
# Successful recovered P01_op already exists and is skipped; other jobs run once.
bash "$p1_op_launcher" run --group nominal
