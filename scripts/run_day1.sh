#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IIC_OSIC_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RAW_DIR="${PROJECT_ROOT}/results/raw/day1"

mkdir -p \
  "${PROJECT_ROOT}/.cache/matplotlib" \
  "${PROJECT_ROOT}/.cache/fontconfig" \
  "${PROJECT_ROOT}/results/generated/day1" \
  "${RAW_DIR}" \
  "${PROJECT_ROOT}/results/plots"

find "${PROJECT_ROOT}/results/generated/day1" -type f -name '*.spice' -delete

# Remove only the deterministic Day 1 raw products. The names without `_l`
# are legacy outputs retained by older revisions of this runner.
for device in nfet pfet; do
  for length_tag in 0p15 0p3 0p5 0p8 1; do
    rm -f \
      "${RAW_DIR}/${device}_characterization_l${length_tag}.log" \
      "${RAW_DIR}/${device}_characterization_l${length_tag}.tsv" \
      "${RAW_DIR}/${device}_characterization_${length_tag}.log" \
      "${RAW_DIR}/${device}_characterization_${length_tag}.tsv"
  done
done
rm -f \
  "${RAW_DIR}/nmos_current_mirror.log" \
  "${RAW_DIR}/nmos_current_mirror.tsv" \
  "${RAW_DIR}/container_tool_identity.txt"

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
      --output-dir results/generated/day1 \
      --corner tt \
      netlists/day1/nfet_characterization.spice.in \
      netlists/day1/pfet_characterization.spice.in \
      netlists/day1/nmos_current_mirror.spice.in
    model_deck=$(sed -n "s/^\\.lib \"\\([^\"]*\\)\" .*/\\1/p" results/generated/day1/nfet_characterization_l0p15.spice)
    {
      printf "container_architecture=%s\n" "$(uname -m)"
      printf "container_python="
      python3 --version 2>&1
      printf "container_ngspice="
      ngspice --version 2>&1 | sed -n "/ngspice-[0-9]/p"
      printf "pdk_model_deck=%s\n" "${model_deck}"
      printf "pdk_model_deck_sha256="
      sha256sum "${model_deck}" | sed "s/[[:space:]].*$//"
    } > results/raw/day1/container_tool_identity.txt
    for netlist in results/generated/day1/*.spice; do
      stem=$(basename "${netlist}" .spice)
      ngspice -b -o "results/raw/day1/${stem}.log" "${netlist}"
    done
  '

MPLCONFIGDIR="${PROJECT_ROOT}/.cache/matplotlib" \
XDG_CACHE_HOME="${PROJECT_ROOT}/.cache" \
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/analyze_day1.py"

IMAGE_ID="$(docker image inspect --format '{{.Id}}' "${IMAGE}")"
DOCKER_CLIENT_VERSION="$(docker version --format '{{.Client.Version}}')"
DOCKER_SERVER_VERSION="$(docker version --format '{{.Server.Version}}')"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/write_day1_manifest.py" \
  --image-reference "${IMAGE}" \
  --image-id "${IMAGE_ID}" \
  --docker-client-version "${DOCKER_CLIENT_VERSION}" \
  --docker-server-version "${DOCKER_SERVER_VERSION}"
