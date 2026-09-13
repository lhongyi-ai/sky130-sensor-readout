#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo '需要 Linux 已有的 Python 3（不自动安装）。请把这条提示发回。' >&2
  exit 2
fi
exec python3 probe.py "$@"
