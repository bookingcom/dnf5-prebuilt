#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK_FILES=()

for arg in "$@"; do
  if [[ "$arg" == *.lock.json && -f "$arg" ]]; then
    LOCK_FILES+=("$arg")
  else
    base="${arg%_run.sh}"
    if [[ -f "${base}.lock.json" ]]; then
      LOCK_FILES+=("${base}.lock.json")
    elif [[ -f "${arg}.lock.json" ]]; then
      LOCK_FILES+=("${arg}.lock.json")
    fi
  fi
done

if [[ ${#LOCK_FILES[@]} -eq 0 ]]; then
  mapfile -t LOCK_FILES < <(find . -name "*.lock.json" | sort)
fi

if [[ ${#LOCK_FILES[@]} -eq 0 ]]; then
  echo "ERROR: No lock files found to validate!" >&2
  exit 1
fi

echo "Found lock files to validate: ${LOCK_FILES[*]}"
python3 "$SCRIPT_DIR/test_lock_generated.py" "${LOCK_FILES[@]}"
