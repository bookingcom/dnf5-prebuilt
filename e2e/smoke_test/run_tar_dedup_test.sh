#!/bin/bash
set -euo pipefail

UNIT_TEST_BIN="$1"
echo "Running tar_dedup unit tests..."
"${UNIT_TEST_BIN}"
echo "tar_dedup unit tests passed successfully!"
