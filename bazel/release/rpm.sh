#!/bin/sh
# rpm launcher of the dnf5-prebuilt distribution.
#
# Points librpm at the rpm configuration (RPM_CONFIGDIR) bundled in this
# distribution and runs the real binary (libexec/rpm). Can be overridden
# through the environment:
#
#   RPM_CONFIGDIR       rpm configuration directory (default: <prefix>/lib/rpm)
set -eu

# Locate the distribution prefix. Follow symlinks to the launcher (e.g. from a
# bin directory on PATH), but keep the logical path when the layout is complete
# there (e.g. a Bazel runfiles tree, where every file is a symlink).
self=$0
while [ ! -x "$(dirname -- "$self")/../libexec/rpm" ] && [ -L "$self" ]; do
    link=$(readlink -- "$self")
    case $link in
        /*) self=$link ;;
        *) self=$(dirname -- "$self")/$link ;;
    esac
done
prefix=$(CDPATH='' cd -- "$(dirname -- "$self")/.." && pwd)

: "${RPM_CONFIGDIR:=$prefix/lib/rpm}"
export RPM_CONFIGDIR

exec "$prefix/libexec/rpm" "$@"
