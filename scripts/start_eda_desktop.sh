#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_ROOT="${IIC_OSIC_TOOLS_DIR:-${PROJECT_ROOT}/../.tools/IIC-OSIC-TOOLS}"
WEB_PORT="${IIC_WEB_PORT:-8080}"
VNC_PORT_HOST="${IIC_VNC_PORT:-5901}"
VNC_PASSWORD="${VNC_PW:-ota130}"

if [[ ! -x "${TOOLS_ROOT}/start_vnc.sh" ]]; then
  echo "IIC-OSIC-TOOLS was not found at ${TOOLS_ROOT}."
  echo "Set IIC_OSIC_TOOLS_DIR to the cloned upstream repository."
  exit 1
fi

export DESIGNS="${PROJECT_ROOT}"
export WEBSERVER_PORT=0
export VNC_PORT=0
export VNC_PW="${VNC_PASSWORD}"
export CONTAINER_NAME="sky130-two-stage-ota-vnc"
export DOCKER_EXTRA_PARAMS="${DOCKER_EXTRA_PARAMS:-} -p 127.0.0.1:${WEB_PORT}:80 -p 127.0.0.1:${VNC_PORT_HOST}:5901"

"${TOOLS_ROOT}/start_vnc.sh"

echo "EDA desktop: http://localhost:${WEB_PORT}/?password=${VNC_PASSWORD}"

