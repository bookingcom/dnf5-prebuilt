#!/bin/bash
set -euo pipefail

CURL_BIN="$1"
LIBCURL_SO="$2"
LIBCURL_REAL_SO="$3"
LICENSES_DIR="$4"
UNIT_TEST_BIN="$5"

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

echo "Checking libcurl symlink target dereferencing: ${LIBCURL_SO} vs ${LIBCURL_REAL_SO}"
if [[ ! -f "${LIBCURL_SO}" ]]; then
  echo "Error: libcurl '${LIBCURL_SO}' does not exist or is not a file" >&2
  exit 1
fi
if [[ ! -s "${LIBCURL_SO}" ]]; then
  echo "Error: libcurl '${LIBCURL_SO}' is empty" >&2
  exit 1
fi
if [[ ! -f "${LIBCURL_REAL_SO}" ]]; then
  echo "Error: real libcurl '${LIBCURL_REAL_SO}' does not exist or is not a file" >&2
  exit 1
fi

# Verify extracted artifact on disk is not a symlink
ACTUAL_SO=$(readlink "${LIBCURL_SO}" || echo "${LIBCURL_SO}")
if [[ -L "${ACTUAL_SO}" ]]; then
  echo "Error: extracted artifact '${ACTUAL_SO}' is a symlink, expected it to be dereferenced" >&2
  exit 1
fi

ACTUAL_REAL_SO=$(readlink "${LIBCURL_REAL_SO}" || echo "${LIBCURL_REAL_SO}")
if [[ -L "${ACTUAL_REAL_SO}" ]]; then
  echo "Error: extracted artifact '${ACTUAL_REAL_SO}' is a symlink, expected it to be dereferenced" >&2
  exit 1
fi

# Verify dereferencing: libcurl.so.4 must be byte-for-byte identical to libcurl.so.4.7.0
echo "Comparing ${LIBCURL_SO} and ${LIBCURL_REAL_SO} with cmp..."
cmp "${LIBCURL_SO}" "${LIBCURL_REAL_SO}"

echo "Checking licenses directory: ${LICENSES_DIR}"
if [[ ! -d "${LICENSES_DIR}" ]]; then
  echo "Error: licenses dir '${LICENSES_DIR}' does not exist or is not a directory" >&2
  exit 1
fi
if [[ ! -f "${LICENSES_DIR}/COPYING" ]]; then
  echo "Error: expected '${LICENSES_DIR}/COPYING' to exist" >&2
  exit 1
fi

# Verify no extracted files in the directory are symlinks (all dereferenced)
for f in "${LICENSES_DIR}"/*; do
  ACTUAL_F=$(readlink "${f}" || echo "${f}")
  if [[ -L "${ACTUAL_F}" ]]; then
    echo "Error: extracted artifact in directory '${ACTUAL_F}' is a symlink, expected regular file" >&2
    exit 1
  fi
done

echo "Running unit tests covering absolute links, climbing links, cross-RPM links, install order, and errors..."
"${UNIT_TEST_BIN}"

echo "All rpm_extract checks passed successfully!"
