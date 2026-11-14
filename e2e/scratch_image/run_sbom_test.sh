#!/usr/bin/env bash
set -euo pipefail

RUNNER="$1"
shift

exec "${RUNNER}" "$@"
