#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'An existing Python 3 installation on Linux is required (no automatic installation). Please return this message.' >&2
  exit 2
fi
exec python3 probe.py "$@"
