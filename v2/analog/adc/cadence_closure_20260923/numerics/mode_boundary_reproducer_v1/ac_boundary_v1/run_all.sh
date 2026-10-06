#!/bin/bash
# Seven independent runs, strictly serial; stop and preserve evidence on failure.
set -euo pipefail
P1_ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
P1_BUDGET=${1:-60}
for P1_CASE in dn20u dn5u dn1u d0 dp1u dp5u dp20u; do
    bash "$P1_ROOT/run_case.sh" "$P1_CASE" "$P1_BUDGET"
done
