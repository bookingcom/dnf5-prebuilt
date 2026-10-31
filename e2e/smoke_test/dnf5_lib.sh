#!/usr/bin/env bash
# Shared by the dnf5 tests: expands the dnf_config preamble (one argument per line, path tokens unexpanded).
#   dnf5_preamble <dnf.conf of the dnf_config target> <repository directory> <scratch directory>
# fills the PREAMBLE array. Paths are relative to the current directory (the runfiles root) or absolute.

dnf5_preamble() {
  local conf="$1" confdir repodir line
  confdir="$(cd "$(dirname "${conf}")" && pwd)"
  repodir="$(cd "$2" && pwd)"
  PREAMBLE=()
  while IFS= read -r line; do
    line="${line//@CONFDIR@/${confdir}}"
    line="${line//@REPODIR@/${repodir}}"
    line="${line//@TMP@/$3}"
    PREAMBLE+=("${line}")
  done <"${confdir}/preamble.args"
}

# dnf5_scratch: SCRATCH is a fresh temporary directory removed on exit, WORK is the (created) directory below it that
# the test hands to dnf5 as its scratch directory.
dnf5_scratch() {
  SCRATCH="$(mktemp -d)"
  WORK="${SCRATCH}/work"
  trap 'rm -rf "${SCRATCH}"' EXIT
  mkdir -p "${WORK}"
}

# repo_section <id> <baseurl> [extra key=value...]: one .repo file section on stdout.
repo_section() {
  local id="$1" baseurl="$2"
  shift 2
  printf '[%s]\nname=%s\nbaseurl=%s\nenabled=1\ngpgcheck=0\n' "${id}" "${id}" "${baseurl}"
  [[ "$#" -eq 0 ]] || printf '%s\n' "$@"
  echo
}

# dnf5_check_solver <dnf5> <options...>: repoquery lists curl, and installing it only reports the missing dependencies
# (the installroot is empty). Needs WORK (dnf5_scratch).
dnf5_check_solver() {
  local dnf5="$1" rc=0 available out
  shift
  echo "=== repoquery --available ==="
  available="$("${dnf5}" repoquery --available "$@" 2>"${WORK}/repoquery.err")" || rc=$?
  cat "${WORK}/repoquery.err"
  echo "exit code: ${rc}"
  test "${rc}" -eq 0
  echo "${available}"
  grep -q '^curl-0:7.76.1-40.el9_8.8.x86_64$' <<<"${available}"

  echo "=== install --assumeno (dependencies are absent in the installroot, so the solver must report them) ==="
  rc=0
  out="$("${dnf5}" install --assumeno curl "$@" 2>&1)" || rc=$?
  echo "${out}"
  echo "exit code: ${rc}"
  # The solver cannot satisfy the glibc requirement, which is an error (1), not a crash (>= 128) or success.
  test "${rc}" -eq 1
  grep -q 'nothing provides' <<<"${out}"
}
