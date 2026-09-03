#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IIC_OSIC_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p \
  "${PROJECT_ROOT}/.cache/matplotlib" \
  "${PROJECT_ROOT}/.cache/fontconfig" \
  "${PROJECT_ROOT}/results/generated/day3" \
  "${PROJECT_ROOT}/results/raw/day3" \
  "${PROJECT_ROOT}/results/plots"

find "${PROJECT_ROOT}/results/generated/day3" -maxdepth 1 -type f -delete
find "${PROJECT_ROOT}/results/raw/day3" -maxdepth 1 -type f -delete

docker run --rm \
  --security-opt seccomp=unconfined \
  --mount "type=bind,source=${PROJECT_ROOT},target=/foss/designs/sky130-two-stage-ota" \
  --workdir /foss/designs/sky130-two-stage-ota \
  --entrypoint /bin/bash \
  "${IMAGE}" \
  -lc '
    set -euo pipefail
    export SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice

    python3 scripts/render_day3.py balance
    ngspice -b -o results/raw/day3/second_stage_balance.log results/generated/day3/second_stage_balance.spice

    python3 scripts/render_day3.py loopgain
    for deck in results/generated/day3/cc*.spice; do
      name="$(basename "${deck}" .spice)"
      ngspice -b -o "results/raw/day3/${name}.log" "${deck}"
    done

    python3 scripts/render_day3.py transient
    ngspice -b -o results/raw/day3/nominal_transient.log results/generated/day3/nominal_transient.spice
  '

MPLCONFIGDIR="${PROJECT_ROOT}/.cache/matplotlib" \
XDG_CACHE_HOME="${PROJECT_ROOT}/.cache" \
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/analyze_day3.py"
