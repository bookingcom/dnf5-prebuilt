#!/usr/bin/env bash
# Runs the rpm binary: version check and showrc to verify macros and configuration
# are loaded from the distribution.
set -euo pipefail

"$RPM" --version | tee version.txt
grep -q "^RPM version " version.txt

"$RPM" --showrc | tee showrc.txt
grep -q "Features supported by rpmlib" showrc.txt

echo "rpm smoke test passed"
