#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_stage() {
  local label="$1"
  local script="$2"
  printf '\n[%s] %s\n' "${label}" "${script#"${PROJECT_ROOT}/"}"
  "${script}"
}

command -v docker >/dev/null 2>&1 || {
  printf 'ERROR: Docker is required but was not found.\n' >&2
  exit 1
}

docker info >/dev/null 2>&1 || {
  printf 'ERROR: The Docker engine is not running. Start Colima first.\n' >&2
  exit 1
}

run_stage "Day 1/5" "${PROJECT_ROOT}/scripts/run_day1.sh"
run_stage "Day 2/5" "${PROJECT_ROOT}/scripts/run_day2.sh"
run_stage "Day 3/5" "${PROJECT_ROOT}/scripts/run_day3.sh"
run_stage "Day 4/5" "${PROJECT_ROOT}/scripts/run_day4.sh"
run_stage "Day 5/5" "${PROJECT_ROOT}/experiments/day5/run.sh"

python3 "${PROJECT_ROOT}/scripts/check_final_schematic.py"

printf '\nAll five simulation stages and the final schematic check passed.\n'
