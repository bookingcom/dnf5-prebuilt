#!/usr/bin/env python3
"""Injects an rpmdb SQLite database into a tar archive at usr/lib/sysimage/rpm/."""

import argparse
import os
import sys
import tarfile


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject rpmdb into a tar archive.")
    parser.add_argument("--input", required=True, help="Path to input uncompressed tar archive")
    parser.add_argument("--rpmdb", required=True, help="Path to rpmdb.sqlite file")
    parser.add_argument("--output", required=True, help="Path to output tar archive")
    args = parser.parse_args()

    seen_entries = set()

    with tarfile.open(args.input, mode="r:") as src, \
         tarfile.open(args.output, mode="w:") as dst:
        for member in src:
            seen_entries.add(member.name.rstrip("/"))
            if member.isreg():
                with src.extractfile(member) as f:
                    dst.addfile(member, fileobj=f)
            else:
                dst.addfile(member)

        # Ensure parent directories exist
        for d in [
            "usr",
            "usr/lib",
            "usr/lib/sysimage",
            "usr/lib/sysimage/rpm",
            "var",
            "var/lib",
            "var/lib/rpm",
        ]:
            if d not in seen_entries:
                seen_entries.add(d)
                dir_ti = tarfile.TarInfo(name=d)
                dir_ti.type = tarfile.DIRTYPE
                dir_ti.mode = 0o755
                dir_ti.uid = 0
                dir_ti.gid = 0
                dir_ti.mtime = 0
                dst.addfile(dir_ti)

        # Inject rpmdb.sqlite
        rpmdb_name = "usr/lib/sysimage/rpm/rpmdb.sqlite"
        rpmdb_size = os.path.getsize(args.rpmdb)
        rpmdb_ti = tarfile.TarInfo(name=rpmdb_name)
        rpmdb_ti.type = tarfile.REGTYPE
        rpmdb_ti.size = rpmdb_size
        rpmdb_ti.mode = 0o644
        rpmdb_ti.uid = 0
        rpmdb_ti.gid = 0
        rpmdb_ti.mtime = 0
        with open(args.rpmdb, "rb") as f:
            dst.addfile(rpmdb_ti, fileobj=f)

        # Add compatibility symlink var/lib/rpm/rpmdb.sqlite -> /usr/lib/sysimage/rpm/rpmdb.sqlite
        link_name = "var/lib/rpm/rpmdb.sqlite"
        link_ti = tarfile.TarInfo(name=link_name)
        link_ti.type = tarfile.SYMTYPE
        link_ti.linkname = "/usr/lib/sysimage/rpm/rpmdb.sqlite"
        link_ti.mode = 0o777
        link_ti.uid = 0
        link_ti.gid = 0
        link_ti.mtime = 0
        dst.addfile(link_ti)

    return 0


if __name__ == "__main__":
    sys.exit(main())
