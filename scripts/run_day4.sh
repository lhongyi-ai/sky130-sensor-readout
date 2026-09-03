#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IIC_OSIC_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DAY4_JOBS="${DAY4_JOBS:-2}"

mkdir -p \
  "${PROJECT_ROOT}/.cache/matplotlib" \
  "${PROJECT_ROOT}/.cache/fontconfig" \
  "${PROJECT_ROOT}/results/generated/day4" \
  "${PROJECT_ROOT}/results/raw/day4" \
  "${PROJECT_ROOT}/results/plots"

find "${PROJECT_ROOT}/results/generated/day4" -mindepth 1 -type f -delete
find "${PROJECT_ROOT}/results/raw/day4" -mindepth 1 -type f -delete

docker run --rm \
  --security-opt seccomp=unconfined \
  --mount "type=bind,source=${PROJECT_ROOT},target=/foss/designs/sky130-two-stage-ota" \
  --workdir /foss/designs/sky130-two-stage-ota \
  --entrypoint /bin/bash \
  "${IMAGE}" \
  -lc "
    set -euo pipefail
    export SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice
    python3 scripts/render_day4.py
    find results/generated/day4 -type f -name '*.spice' ! -name 'ota_subckt.spice' -print0 \
      | sort -z \
      | xargs -0 -n 1 -P '${DAY4_JOBS}' bash scripts/run_day4_deck.sh
  "

MPLCONFIGDIR="${PROJECT_ROOT}/.cache/matplotlib" \
XDG_CACHE_HOME="${PROJECT_ROOT}/.cache" \
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/analyze_day4.py"
