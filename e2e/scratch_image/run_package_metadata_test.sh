#!/usr/bin/env bash
set -euo pipefail

TEST_BIN="$1"
shift

exec "${TEST_BIN}" "$@"
