#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IIC_OSIC_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p \
  "${PROJECT_ROOT}/.cache/matplotlib" \
  "${PROJECT_ROOT}/.cache/fontconfig" \
  "${PROJECT_ROOT}/results/generated/day2" \
  "${PROJECT_ROOT}/results/raw/day2" \
  "${PROJECT_ROOT}/results/plots"

find "${PROJECT_ROOT}/results/generated/day2" -type f -name '*.spice' -delete
find "${PROJECT_ROOT}/results/raw/day2" -maxdepth 1 -type f -name 'first_stage_*.tsv' -delete

docker run --rm \
  --security-opt seccomp=unconfined \
  --mount "type=bind,source=${PROJECT_ROOT},target=/foss/designs/sky130-two-stage-ota" \
  --workdir /foss/designs/sky130-two-stage-ota \
  --entrypoint /bin/bash \
  "${IMAGE}" \
  -lc '
    set -euo pipefail
    export SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice
    python3 scripts/render_netlists.py \
      --output-dir results/generated/day2 \
      --corner tt \
      netlists/day2/first_stage_characterization.spice.in
    ngspice -b \
      -o results/raw/day2/first_stage_characterization.log \
      results/generated/day2/first_stage_characterization.spice
  '

MPLCONFIGDIR="${PROJECT_ROOT}/.cache/matplotlib" \
XDG_CACHE_HOME="${PROJECT_ROOT}/.cache" \
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/analyze_day2.py"
