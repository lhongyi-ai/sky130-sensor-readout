#!/bin/bash
set -uo pipefail
spectre -W >spectre_version.txt 2>&1
spectre -h options >options_help.txt 2>&1
spectre -h tran >tran_help.txt 2>&1
command -v spectre >spectre_path.txt
printf '0\n' >exit_code.txt
