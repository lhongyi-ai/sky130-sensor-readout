#!/usr/bin/env bash
set -euo pipefail
p1_fix_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
env -u LD_LIBRARY_PATH python3 "$p1_fix_dir/install.py" "${1:-$p1_fix_dir/../basic_design_v1_0_4}"
