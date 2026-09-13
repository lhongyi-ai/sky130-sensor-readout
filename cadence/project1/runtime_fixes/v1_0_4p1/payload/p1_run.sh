#!/usr/bin/env bash
# Keep Cadence's shared-library environment out of the system Python process.
set -euo pipefail
p1_script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export P1_RUNTIME_LD_LIBRARY_PATH="${LD_LIBRARY_PATH-}"
unset LD_LIBRARY_PATH
exec python3 "$p1_script_dir/run.py" "$@"
