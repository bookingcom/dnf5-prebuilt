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

echo "Scratch container validation passed successfully!"
