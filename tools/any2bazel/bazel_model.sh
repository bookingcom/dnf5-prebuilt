#!/bin/bash
# Extracts the any2bazel model of the Bazel build of @dnf5 and diffs it
# against the reference model.
#
# Usage: tools/any2bazel/bazel_model.sh <workdir>   (run from the repo root)
#   ANY2BAZEL_SCRIPTS  any2bazel scripts dir (default ~/.agents/skills/any2bazel/scripts)
set -euo pipefail

mkdir -p "${1:?usage: $0 <workdir>}"
work=$(cd "$1" && pwd)
scripts=${ANY2BAZEL_SCRIPTS:-$HOME/.agents/skills/any2bazel/scripts}
root=$(pwd)

# Mirror the reference: Linux x86_64, RelWithDebInfo (-c opt). Param files
# are disabled because aquery does not materialize them; --nostart_end_lib
# makes external libraries visible as archives so link deps can be inferred.
bazel aquery 'mnemonic("CppCompile|ObjcCompile|CppLink|CppArchive", @dnf5//...)' \
    --config=linux_amd64 -c opt --nostart_end_lib \
    --features=-compiler_param_file --features=-linker_param_file \
    --output=jsonproto >"$work/aquery.raw.json"

# Make @dnf5 paths repository-relative, like the reference's /src-relative ones.
canonical="external/$(bazel mod dump_repo_mapping '' 2>/dev/null | jq -r '.dnf5')"
sed "s#${canonical}/##g" "$work/aquery.raw.json" >"$work/aquery.json"

(cd "$work" && python3 "$scripts/extract_bazel.py" aquery.json . model.bazel.json)
(cd "$work" && python3 "$scripts/diff.py" model.cmake.json model.bazel.json "$root/any2bazel.json" >diff.json) || true
python3 "$scripts/triage.py" "$work/diff.json"
