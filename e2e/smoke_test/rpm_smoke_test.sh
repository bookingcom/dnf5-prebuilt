#!/usr/bin/env bash
# Runs the rpm binary: version check, showrc, and query installed packages in marked rpmdbs.
set -euo pipefail

"$RPM" --version | tee version.txt
grep -q "^RPM version " version.txt

"$RPM" --showrc | tee showrc.txt
grep -q "Features supported by rpmlib" showrc.txt

# Validate that rpm can see the respective RPMs marked as installed
WORK="${TEST_TMPDIR:-$(mktemp -d)}/rpmdb_check"

# 1. Base DB has only libcurl
mkdir -p "${WORK}/base"
cp "$RPMDB_BASE" "${WORK}/base/rpmdb.sqlite"
PKGS_BASE="$("$RPM" --dbpath "${WORK}/base" -qa | sort)"
test "$PKGS_BASE" = "libcurl-7.76.1-40.el9_8.8.x86_64"

# 2. Single DB marked with curl and libcurl
mkdir -p "${WORK}/single"
cp "$RPMDB_SINGLE" "${WORK}/single/rpmdb.sqlite"
PKGS_SINGLE="$("$RPM" --dbpath "${WORK}/single" -qa | sort)"
test "$PKGS_SINGLE" = "$(printf "curl-7.76.1-40.el9_8.8.x86_64\nlibcurl-7.76.1-40.el9_8.8.x86_64")"

# 3. Layered DB marked with curl on top of base DB
mkdir -p "${WORK}/layered"
cp "$RPMDB_LAYERED" "${WORK}/layered/rpmdb.sqlite"
PKGS_LAYERED="$("$RPM" --dbpath "${WORK}/layered" -qa | sort)"
test "$PKGS_LAYERED" = "$(printf "curl-7.76.1-40.el9_8.8.x86_64\nlibcurl-7.76.1-40.el9_8.8.x86_64")"

echo "rpm smoke test passed"
