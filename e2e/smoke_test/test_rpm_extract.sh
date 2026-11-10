#!/bin/bash
set -euo pipefail

CURL_BIN="$1"
LIBCURL_SO="$2"
LICENSES_DIR="$3"

echo "Checking curl binary: ${CURL_BIN}"
if [[ ! -f "${CURL_BIN}" ]]; then
  echo "Error: curl binary '${CURL_BIN}' does not exist or is not a file" >&2
  exit 1
fi
if [[ ! -x "${CURL_BIN}" ]]; then
  echo "Error: curl binary '${CURL_BIN}' is not executable" >&2
  exit 1
fi
ACTUAL_CURL=$(readlink "${CURL_BIN}" || echo "${CURL_BIN}")
if [[ -L "${ACTUAL_CURL}" ]]; then
  echo "Error: extracted artifact '${ACTUAL_CURL}' is a symlink, expected regular file" >&2
  exit 1
fi

echo "Checking libcurl library: ${LIBCURL_SO}"
if [[ ! -f "${LIBCURL_SO}" ]]; then
  echo "Error: libcurl '${LIBCURL_SO}' does not exist or is not a file" >&2
  exit 1
fi
if [[ ! -s "${LIBCURL_SO}" ]]; then
  echo "Error: libcurl '${LIBCURL_SO}' is empty" >&2
  exit 1
fi
# Verify that the extracted artifact is dereferenced and not a symlink in the output tree
ACTUAL_SO=$(readlink "${LIBCURL_SO}" || echo "${LIBCURL_SO}")
if [[ -L "${ACTUAL_SO}" ]]; then
  echo "Error: extracted artifact '${ACTUAL_SO}' is a symlink, expected it to be dereferenced" >&2
  exit 1
fi

echo "Checking licenses directory: ${LICENSES_DIR}"
if [[ ! -d "${LICENSES_DIR}" ]]; then
  echo "Error: licenses dir '${LICENSES_DIR}' does not exist or is not a directory" >&2
  exit 1
fi
if [[ ! -f "${LICENSES_DIR}/COPYING" ]]; then
  echo "Error: expected '${LICENSES_DIR}/COPYING' to exist" >&2
  exit 1
fi

echo "All rpm_extract checks passed successfully!"
