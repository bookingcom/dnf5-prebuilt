#!/bin/bash
# Produces the any2bazel reference model (model.cmake.json) of the upstream
# dnf5 CMake build. Requires docker and the any2bazel skill scripts.
#
# Usage: tools/any2bazel/reference.sh <workdir>
#   ANY2BAZEL_SCRIPTS  any2bazel scripts dir (default ~/.agents/skills/any2bazel/scripts)
#   FEDORA_IMAGE       container image providing the dnf5 build deps (default fedora:44)
set -euo pipefail

mkdir -p "${1:?usage: $0 <workdir>}"
work=$(cd "$1" && pwd)
scripts=${ANY2BAZEL_SCRIPTS:-$HOME/.agents/skills/any2bazel/scripts}
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
version=$(sed -n 's/^DNF5_VERSION = "\(.*\)"/\1/p' "$root/bazel/extensions.bzl")

mkdir -p "$work/build" "$work/dl"
if [ ! -d "$work/src" ]; then
    curl -sfL -o "$work/dl/dnf5.tar.gz" \
        "https://github.com/rpm-software-management/dnf5/archive/refs/tags/$version.tar.gz"
    mkdir -p "$work/src"
    tar xzf "$work/dl/dnf5.tar.gz" -C "$work/src" --strip-components=1
fi

docker run --rm \
    -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
    -v "$work/src:/src" -v "$work/build:/build" \
    -v "$here/reference_configure.sh:/reference_configure.sh:ro" \
    "${FEDORA_IMAGE:-fedora:44}" bash /reference_configure.sh

# The reference keys translation units relative to /src (the container path).
(cd "$work" && python3 "$scripts/extract_cmake.py" build /src model.cmake.json build/trace.jsonl)
echo "wrote $work/model.cmake.json (dependency versions: $work/build/versions.txt)"
