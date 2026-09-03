#!/usr/bin/env bash
set -u

deck="$1"
relative="${deck#results/generated/day4/}"
stem="${relative%.spice}"
log="results/raw/day4/logs/${stem}.log"
exit_file="results/raw/day4/logs/${stem}.exit_code"
mkdir -p "$(dirname "${log}")"

ngspice -b -o "${log}" "${deck}"
code=$?
printf '%s\n' "${code}" > "${exit_file}"
exit 0
