#!/usr/bin/env bash
# project1 school launcher v1. Restores the environment observed in the working
# IC618 GUI and the successful Spectre resistor run. No schematic/database edits.
# Download this file to ~/cadence_skywater/ and invoke it with bash.
set -euo pipefail

p1_cadence_root="${P1_SCHOOL_CADENCE_ROOT:-/project/engineering/cadence21}"
p1_package_dir="${P1_BASIC_PACKAGE_DIR:-$HOME/cadence_skywater/project1_handoff/basic_design_v1_0_4}"
export CDSHOME="$p1_cadence_root/ic"
export PATH="$CDSHOME/bin:$p1_cadence_root/spectre/tools/bin:$PATH"

# The working GUI had CDS_LIC_FILE unset and used LM_LICENSE_FILE.
# This is a server locator, not a license file or key.
unset CDS_LIC_FILE
export LM_LICENSE_FILE="${P1_SCHOOL_LICENSE_SERVER:-27021@licensing02.seas.wustl.edu}"

# Reconstruct the known-working GUI shared-library search path. p1_run.sh will
# remove it before starting system Python; run.py passes it only to tool children.
p1_library_dirs=(
    "$CDSHOME/share/oa/lib/linux_rhel60_64/opt"
    "$CDSHOME/tools.lnx86/dfII/lib/64bit"
    "$CDSHOME/tools.lnx86/sev/lib/64bit"
    "$CDSHOME/tools.lnx86/lib/64bit"
    "$CDSHOME/tools.lnx86/lib"
    "$CDSHOME/tools.lnx86/hdf5/lib/64bit"
    "$CDSHOME/tools.lnx86/lz4/lib/64bit"
    "$CDSHOME/tools.lnx86/python/64bit/lib"
    "$p1_cadence_root/incisive/tools.lnx86/lib/64bit"
    "$CDSHOME/tools.lnx86/TPtools/grpc/lib64"
    "$CDSHOME/tools.lnx86/TPtools/grpc/lib"
    "$CDSHOME/tools.lnx86/Qt/v5/64bit/lib"
    /lib64
    "$p1_cadence_root/lib"
)
export LD_LIBRARY_PATH="$(IFS=:; printf '%s' "${p1_library_dirs[*]}")"

if [[ ! -x "$CDSHOME/bin/virtuoso" ]]; then
    printf 'P1_SCHOOL_ENV_STOPPED: Virtuoso launcher missing: %s\n' "$CDSHOME/bin/virtuoso" >&2
    exit 2
fi
if [[ ! -f "$p1_package_dir/p1_run.sh" || ! -f "$p1_package_dir/run.py" ]]; then
    printf 'P1_SCHOOL_ENV_STOPPED: basic_design_v1_0_4 with runtime patch 1.0.4p1 is required at %s\n' "$p1_package_dir" >&2
    exit 2
fi
if [[ $# -eq 0 ]]; then
    printf 'Usage: bash p1_school_run_v1.sh run --job mim_ac --retry\n       bash p1_school_run_v1.sh collect\n' >&2
    exit 2
fi
cd -- "$p1_package_dir"
exec bash "$p1_package_dir/p1_run.sh" "$@"
