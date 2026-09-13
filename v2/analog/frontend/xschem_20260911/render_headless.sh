#!/usr/bin/env bash
set -euo pipefail

render_dir="renders"
display_id=":117"
mkdir -p "${render_dir}"

if [[ -e /tmp/.X11-unix/X117 ]]; then
  echo "Display ${display_id} is already in use." >&2
  exit 2
fi

Xvfb "${display_id}" -screen 0 1920x1280x24 -nolisten tcp >"${render_dir}/xvfb.log" 2>&1 &
xvfb_pid=$!
cleanup() {
  kill "${xvfb_pid}" 2>/dev/null || true
  wait "${xvfb_pid}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
sleep 1

render_page() {
  local schematic=$1
  local stem=$2
  local png_command
  local svg_command
  png_command="xschem zoom_full; xschem print png ${render_dir}/${stem}.png 2400 1600; exit"
  svg_command="xschem zoom_full; xschem print svg ${render_dir}/${stem}.svg 2400 1600; exit"
  timeout 25s env DISPLAY="${display_id}" /foss/tools/bin/xschem \
    --command "${png_command}" "${schematic}" \
    >"${render_dir}/${stem}.log" 2>&1
  timeout 25s env DISPLAY="${display_id}" /foss/tools/bin/xschem \
    --command "${svg_command}" "${schematic}" \
    >>"${render_dir}/${stem}.log" 2>&1
  test -s "${render_dir}/${stem}.png"
  test -s "${render_dir}/${stem}.svg"
}

render_page frontend_top.sch frontend_top
render_page sky130_v2_switchable_pga.sch switchable_pga
render_page rd_fdota.sch rd_fdota

echo "Rendered 3 Xschem pages to ${render_dir}/ and stopped Xvfb PID ${xvfb_pid}."
