#!/bin/sh
# dnf5 launcher of the dnf5-prebuilt distribution.
#
# Points dnf5, libdnf5 and librpm at the plugins and configuration bundled in
# this distribution and runs the real binary (libexec/dnf5). Every default can
# be overridden through the environment or on the command line:
#
#   RPM_CONFIGDIR       rpm configuration directory  (default: <prefix>/lib/rpm)
#   DNF5_PLUGINS_DIR    dnf5 command plugins         (default: <prefix>/lib/dnf5/plugins)
#   SSL_CERT_FILE       CA bundle for HTTPS repositories
#                       (default: the first system bundle found)
#   DNF5_PREBUILT_NO_DEFAULTS=1
#                       do not add the --setopt defaults below
set -eu

# Locate the distribution prefix. Follow symlinks to the launcher (e.g. from a
# bin directory on PATH), but keep the logical path when the layout is complete
# there (e.g. a Bazel runfiles tree, where every file is a symlink).
self=$0
while [ ! -x "$(dirname -- "$self")/../libexec/dnf5" ] && [ -L "$self" ]; do
    link=$(readlink -- "$self")
    case $link in
        /*) self=$link ;;
        *) self=$(dirname -- "$self")/$link ;;
    esac
done
prefix=$(CDPATH='' cd -- "$(dirname -- "$self")/.." && pwd)

: "${RPM_CONFIGDIR:=$prefix/lib/rpm}"
: "${DNF5_PLUGINS_DIR:=$prefix/lib/dnf5/plugins/}"
export RPM_CONFIGDIR DNF5_PLUGINS_DIR

if [ -z "${DNF5_PREBUILT_NO_DEFAULTS:-}" ]; then
    cacert=${SSL_CERT_FILE:-}
    if [ -z "$cacert" ]; then
        # Fedora/RHEL, Debian/Ubuntu, openSUSE, macOS/Alpine/Arch
        for f in /etc/pki/tls/certs/ca-bundle.crt /etc/ssl/certs/ca-certificates.crt \
            /etc/ssl/ca-bundle.pem /etc/ssl/cert.pem; do
            if [ -r "$f" ]; then
                cacert=$f
                break
            fi
        done
    fi
    if [ -n "$cacert" ]; then
        set -- "--setopt=sslcacert=$cacert" "$@"
    fi
    set -- \
        "--setopt=pluginpath=$prefix/lib/libdnf5/plugins" \
        "--setopt=pluginconfpath=$prefix/etc/dnf/libdnf5-plugins" \
        "$@"
fi

for arg in "$@"; do
    case "$arg" in
        rpmdb-mark)
            exec "${PYTHON3:-python3}" "$prefix/lib/rpm_tools/rpm_mark.py" --dnf5="$self" --rpm="$prefix/bin/rpm" "$@"
            ;;
    esac
done

exec "$prefix/libexec/dnf5" "$@"
