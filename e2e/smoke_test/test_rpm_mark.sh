#!/usr/bin/env bash
# rpm_mark and the standalone `dnf5 rpmdb-mark` write an rpmdb with exactly curl and its dependency libcurl.
set -euo pipefail

DNF5_RPMDB_DIR="$1"
DNF5="$2"
CONF="$3"
REPO_DIR="$4"

source "$(dirname "$0")/dnf5_lib.sh"

# The package keys of an rpmdb: names, header digests and provides, one "table key" per line, sorted. Not the bytes of
# the database, which hold the install time.
keys() {
  python3 -I -c "
import sqlite3, sys
con = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
for table in ('Name', 'Sha1header', 'Providename'):
    for (key,) in con.execute('SELECT DISTINCT key FROM ' + table):
        print(table, key)
" "$1" | sort
}

echo "=== 1. rpm_mark generated an rpmdb holding exactly curl and libcurl ==="
SQLITE_DB="${DNF5_RPMDB_DIR}/var/lib/rpm/rpmdb.sqlite"
test -f "${SQLITE_DB}"
expect_packages() {
  diff <(printf 'Name curl\nName libcurl\n') <(keys "$1" | grep '^Name ')
  test "$(python3 -I -c "
import sqlite3, sys
print(sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True).execute('SELECT count(*) FROM Packages').fetchone()[0])
" "$1")" = 2
}
expect_packages "${SQLITE_DB}"

echo "=== 2. Standalone dnf5 rpmdb-mark on a staging root, unprivileged ==="
dnf5_scratch
mkdir -p "${WORK}/root"
dnf5_preamble "${CONF}" "${REPO_DIR}" "${WORK}"
STAGING_ROOT="${WORK}/multistage_docker_image"
"${DNF5}" "${PREAMBLE[@]}" rpmdb-mark --rpmdb-root="${STAGING_ROOT}" --archlist=x86_64 "curl=7.76.1-40.el9_8.8"
expect_packages "${STAGING_ROOT}/var/lib/rpm/rpmdb.sqlite"
diff <(keys "${SQLITE_DB}") <(keys "${STAGING_ROOT}/var/lib/rpm/rpmdb.sqlite")

echo "=== 3. --nodeps marks the named package alone, a plain name finds the newest ==="
"${DNF5}" "${PREAMBLE[@]}" rpmdb-mark --rpmdb-root="${WORK}/nodeps" --archlist=x86_64 --nodeps curl
keys "${WORK}/nodeps/var/lib/rpm/rpmdb.sqlite" | grep -qx 'Name curl'
! keys "${WORK}/nodeps/var/lib/rpm/rpmdb.sqlite" | grep -qx 'Name libcurl'

echo "=== 4. An unknown package fails and writes no database ==="
if "${DNF5}" "${PREAMBLE[@]}" rpmdb-mark --rpmdb-root="${WORK}/none" --archlist=x86_64 nosuchpkg; then
  echo "Error: marking an unknown package succeeded"
  exit 1
fi
test ! -e "${WORK}/none/var/lib/rpm/rpmdb.sqlite"

echo "=== 5. An --rpmdb-root that normalizes to / is refused ==="
for root in /. // /tmp/..; do
  if "${DNF5}" "${PREAMBLE[@]}" rpmdb-mark --rpmdb-root="${root}" --archlist=x86_64 --nodeps curl 2>"${WORK}/root.err"; then
    echo "Error: --rpmdb-root=${root} was accepted"
    exit 1
  fi
  grep -qF -- "--rpmdb-root must be specified and cannot be '/'" "${WORK}/root.err"
done

echo "=== 6. With SOURCE_DATE_EPOCH the same packages give the same rpmdb ==="
for run in 1 2; do
  SOURCE_DATE_EPOCH=0 "${DNF5}" "${PREAMBLE[@]}" rpmdb-mark --rpmdb-root="${WORK}/repro${run}" --archlist=x86_64 curl
  # INSTALLTIME is in seconds: the second run must be in another one.
  [[ "${run}" -eq 2 ]] || sleep 1
done
cmp "${WORK}/repro1/var/lib/rpm/rpmdb.sqlite" "${WORK}/repro2/var/lib/rpm/rpmdb.sqlite"

echo "ALL TESTS PASSED SUCCESSFULLY!"
