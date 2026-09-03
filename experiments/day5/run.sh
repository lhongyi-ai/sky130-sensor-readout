#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly DAY5_DIR="${PROJECT_ROOT}/experiments/day5"
readonly IMAGE="hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7"
readonly LOCK_DIR="${DAY5_DIR}/.run.lock"
BACKUP_DIR=""
BACKUP_READY=0
RUN_STAGE="lock"

readonly -a OUTPUT_TARGETS=(
  generated
  raw
  day5_manifest.json
  variant_manifest.csv
  generated_inventory.csv
  raw_inventory.csv
  recon_summary.csv
  icmr_checkpoints.csv
  icmr_device_margins.csv
  log_audit.csv
  retained_failure_audit.csv
  decision_summary.csv
  assessment.md
  last_success.json
)

copies_match() {
  local source="$1"
  local copy="$2"
  if [[ -d "${source}" && ! -L "${source}" ]]; then
    [[ -d "${copy}" && ! -L "${copy}" ]] && diff -qr -- "${source}" "${copy}" >/dev/null
  elif [[ -f "${source}" && ! -L "${source}" ]]; then
    [[ -f "${copy}" && ! -L "${copy}" ]] && cmp -s -- "${source}" "${copy}"
  else
    return 1
  fi
}

preserve_recovery_state() {
  local reason="$1"
  local original_code="$2"
  echo "Day 5 recovery stopped safely: ${reason}." >&2
  echo "Current outputs, failed-run archive (if created), and last-good backup are preserved." >&2
  echo "Backup: ${BACKUP_DIR:-NOT_CREATED}; lock retained: ${LOCK_DIR}." >&2
  if [[ "${original_code}" -eq 0 ]]; then
    exit 90
  fi
  exit "${original_code}"
}

archive_and_restore() {
  local original_code="$1"
  trap - EXIT
  set +e
  local archive_stamp archive_dir target base source destination
  archive_stamp="$(date -u '+%Y%m%dT%H%M%SZ')-pid$$"
  archive_dir="${DAY5_DIR}/failed_runs/${archive_stamp}"

  if ! mkdir -p "${DAY5_DIR}/failed_runs" || ! mkdir "${archive_dir}"; then
    preserve_recovery_state "could not create the failed-run archive" "${original_code}"
  fi
  for target in "${OUTPUT_TARGETS[@]}"; do
    source="${DAY5_DIR}/${target}"
    base="${target##*/}"
    destination="${archive_dir}/${base}"
    if [[ -e "${source}" ]]; then
      if ! cp -a "${source}" "${archive_dir}/" || ! copies_match "${source}" "${destination}"; then
        preserve_recovery_state "failed-run archive copy did not verify for ${target}" "${original_code}"
      fi
    fi
  done
  if ! printf 'exit_code=%s\nstage=%s\narchive=%s\nbackup=%s\n' \
    "${original_code}" "${RUN_STAGE}" "${archive_dir}" "${BACKUP_DIR}" > "${archive_dir}/failure_context.txt"; then
    preserve_recovery_state "could not write failure_context.txt" "${original_code}"
  fi

  for target in "${OUTPUT_TARGETS[@]}"; do
    if ! rm -rf "${DAY5_DIR:?}/${target}"; then
      preserve_recovery_state "could not remove failed output ${target} after verified archival" "${original_code}"
    fi
  done
  for target in "${OUTPUT_TARGETS[@]}"; do
    base="${target##*/}"
    source="${BACKUP_DIR}/${base}"
    destination="${DAY5_DIR}/${base}"
    if [[ -e "${source}" ]]; then
      if ! cp -a "${source}" "${DAY5_DIR}/" || ! copies_match "${source}" "${destination}"; then
        preserve_recovery_state "last-good restore did not verify for ${target}" "${original_code}"
      fi
    fi
  done
  if ! rm -rf "${BACKUP_DIR}"; then
    preserve_recovery_state "verified restore succeeded but backup cleanup failed" "${original_code}"
  fi
  BACKUP_DIR=""
  if ! rm -rf "${LOCK_DIR}"; then
    preserve_recovery_state "verified restore succeeded but lock cleanup failed" "${original_code}"
  fi
  echo "Day 5 run failed at ${RUN_STAGE}; failed artifacts are archived at ${archive_dir}; last-good outputs were restored and verified." >&2
  if [[ "${original_code}" -eq 0 ]]; then
    exit 1
  fi
  exit "${original_code}"
}

on_exit() {
  local original_code="$1"
  trap - EXIT
  set +e
  if [[ "${BACKUP_READY}" -ne 1 ]]; then
    if [[ -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
      rm -rf "${BACKUP_DIR}"
    fi
    rm -rf "${LOCK_DIR}"
    echo "Day 5 run failed before a verified snapshot was ready; last-good outputs were never removed." >&2
    if [[ "${original_code}" -eq 0 ]]; then
      exit 1
    fi
    exit "${original_code}"
  fi
  archive_and_restore "${original_code}"
}

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "Day 5 run refused: ${LOCK_DIR} already exists." >&2
  exit 2
fi
trap 'on_exit $?' EXIT
printf '%s\n' "$$" > "${LOCK_DIR}/pid"

RUN_STAGE="snapshot_last_good"
BACKUP_DIR="$(mktemp -d "${DAY5_DIR}/.run-backup.XXXXXX")"
for target in "${OUTPUT_TARGETS[@]}"; do
  if [[ -e "${DAY5_DIR}/${target}" ]]; then
    cp -a "${DAY5_DIR}/${target}" "${BACKUP_DIR}/"
    copies_match "${DAY5_DIR}/${target}" "${BACKUP_DIR}/${target##*/}"
  fi
done
BACKUP_READY=1

RUN_STAGE="generate_and_simulate_32_decks"
docker run --rm \
  --security-opt seccomp=unconfined \
  --mount "type=bind,source=${PROJECT_ROOT},target=/foss/designs/sky130-two-stage-ota" \
  --workdir /foss/designs/sky130-two-stage-ota \
  --entrypoint /bin/bash \
  "${IMAGE}" \
  -lc '
    set -euo pipefail
    export SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice
    python3 experiments/day5/recon.py generate
    overall=0
    while IFS= read -r deck; do
      stem="${deck%.spice}"
      set +e
      ngspice -b \
        -o "experiments/day5/raw/${stem}.log" \
        "experiments/day5/generated/${deck}"
      code=$?
      set -e
      printf "%s\n" "${code}" > "experiments/day5/raw/${stem}.exit_code"
      if [[ "${code}" -ne 0 ]]; then
        overall=1
      fi
    done < experiments/day5/generated/run_list.txt
    exit "${overall}"
  '

RUN_STAGE="strict_analysis_and_integrity_audit"
docker run --rm \
  --security-opt seccomp=unconfined \
  --mount "type=bind,source=${PROJECT_ROOT},target=/foss/designs/sky130-two-stage-ota" \
  --workdir /foss/designs/sky130-two-stage-ota \
  --entrypoint /bin/bash \
  "${IMAGE}" \
  -lc '
    set -euo pipefail
    python3 experiments/day5/recon.py analyze
  '

RUN_STAGE="success_cleanup"
trap - EXIT
cleanup_code=0
rm -rf "${BACKUP_DIR}" || cleanup_code=1
BACKUP_DIR=""
rm -rf "${LOCK_DIR}" || cleanup_code=1
if [[ "${cleanup_code}" -ne 0 ]]; then
  echo "Day 5 evidence passed, but temporary backup/lock cleanup failed; verified outputs were preserved." >&2
  exit 91
fi
echo "DAY5_RUN_OK: 32/32 logs, 48/48 TSVs, and 9/9 CSV artifacts verified."
