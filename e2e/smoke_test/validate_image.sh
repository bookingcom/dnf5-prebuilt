#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-localhost/e2e-curl-test:latest}"

echo "Validating container image: ${IMAGE_TAG}"

# Ensure docker daemon is responsive
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running or not accessible." >&2
  exit 1
fi

echo "Checking package installation in rpmdb..."
docker run --network none --rm "${IMAGE_TAG}" rpm -q curl libcurl

echo "Checking binary execution without network..."
docker run --network none --rm "${IMAGE_TAG}" curl --version

echo "Container validation passed successfully!"
