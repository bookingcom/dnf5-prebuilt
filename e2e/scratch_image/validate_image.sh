#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-localhost/e2e-ol10-scratch-curl:latest}"

echo "Validating scratch container image: ${IMAGE_TAG}"

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running or not accessible." >&2
  exit 1
fi

echo "Checking curl execution without network..."
docker run --network none --rm "${IMAGE_TAG}" curl --version

echo "Checking bash execution..."
docker run --network none --rm "${IMAGE_TAG}" bash --version
docker run --network none --rm "${IMAGE_TAG}" bash -c "echo 'Hello from bash'; curl -V | head -n 1"

echo "Checking that minimal image excludes docs, man pages, licenses, and build-id..."
docker run --network none --rm "${IMAGE_TAG}" bash -c '
  for dir in /usr/share/doc /usr/share/man /usr/share/licenses /usr/lib/.build-id; do
    if [ -d "$dir" ] && [ "$(find "$dir" -type f | wc -l)" -gt 0 ]; then
      echo "Error: Directory $dir contains files in minimal image!" >&2
      exit 1
    fi
  done
'

echo "Checking that install_langs filtered out non-English locales..."
docker run --network none --rm "${IMAGE_TAG}" bash -c '
  for dir in /usr/share/locale/de /usr/share/locale/fr /usr/share/locale/es; do
    if [ -d "$dir" ]; then
      echo "Error: Directory $dir should have been excluded by install_langs!" >&2
      exit 1
    fi
  done
'

echo "Scratch container validation passed successfully!"
