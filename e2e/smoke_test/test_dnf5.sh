#!/usr/bin/env bash
# Smoke test: dnf5 loads a local repository, lists packages and resolves a transaction inside a temporary installroot.
set -euo pipefail

DNF5="$1"
REPO_DIR="$(cd "$2" && pwd)"
NOARCH_RPM="$(cd "$(dirname "$3")" && pwd)/$(basename "$3")"

source "$(dirname "$0")/dnf5_lib.sh"

dnf5_scratch
mkdir -p "${WORK}/repos" "${WORK}/root"
repo_section ol9 "file://${REPO_DIR}" repo_gpgcheck=0 >|"${WORK}/repos/ol9.repo"

opts=(
  --installroot="${WORK}/root"
  --forcearch=x86_64
  --releasever=9
  --setopt=reposdir="${WORK}/repos"
  --setopt=cachedir="${WORK}/cache"
  --setopt=logdir="${WORK}/log"
)

dnf5_check_solver "${DNF5}" "${opts[@]}"

echo "=== a noarch package passes rpm's arch, os and digest checks ==="
# The transaction itself needs chroot(2), so it succeeds only as root. Unprivileged it stops at that step, which
# comes after the checks that used to reject the package (on a macOS host too).
rc=0
out="$("${DNF5}" install --assumeyes --no-gpgchecks "${NOARCH_RPM}" --installroot="${WORK}/root" --releasever=9 \
  --setopt=reposdir="${WORK}/repos" --setopt=cachedir="${WORK}/cache" --setopt=logdir="${WORK}/log" 2>&1)" || rc=$?
echo "${out}"
echo "exit code: ${rc}"
if grep -qE 'different (architecture|operating system)|no signature|does not verify' <<<"${out}"; then
  echo "rpm rejected the package" >&2
  exit 1
fi
if [[ "${rc}" -ne 0 ]]; then
  grep -q 'Unable to change root directory' "${WORK}/log/dnf5.log"
fi

echo "=== rpmdb is created inside the installroot ==="
test -f "${WORK}/root/var/lib/rpm/rpmdb.sqlite"

echo "=== the lock command plugin is installed ==="
help="$("${DNF5}" lock --help)"
grep -q -- "--archlist" <<<"${help}"
grep -q -- "--module-enable" <<<"${help}"

echo "dnf5 smoke test passed"
