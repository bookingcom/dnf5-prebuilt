#!/usr/bin/env python3
"""rpm_mark: records package headers into an rpmdb without installing them, reproducibly."""

import argparse
import os
import shutil
import sqlite3
import subprocess


def main():
    parser = argparse.ArgumentParser(description="rpm_mark tool")
    parser.add_argument("--output", dest="output", required=True, help="Target rpmdb.sqlite file")
    parser.add_argument("--base-rpmdb", dest="base_rpmdb", help="Optional base rpmdb.sqlite file to mark packages on top of")
    parser.add_argument("--rpm", dest="rpm", required=True, help="Path to rpm binary")
    parser.add_argument("rpms", nargs="+", help="RPM files to record into rpmdb")

    args = parser.parse_args()

    os.environ["SOURCE_DATE_EPOCH"] = "0"

    rpm_bin = os.path.abspath(args.rpm)

    stage_dir = os.path.abspath(args.output + ".stage")
    os.makedirs(stage_dir, exist_ok=True)

    stage_db = os.path.join(stage_dir, "rpmdb.sqlite")
    if args.base_rpmdb:
        shutil.copyfile(args.base_rpmdb, stage_db)
        os.chmod(stage_db, 0o644)

    rpm_files = [os.path.abspath(p) for p in args.rpms]

    cmd = [
        rpm_bin,
        "--dbpath", stage_dir,
        "--install",
        "--replacefiles",
        "--replacepkgs",
        "--verbose",
        "--hash",
        "--justdb",
        "--nodeps",
        "--noscripts",
        "--nosignature",
        "--ignorearch",
        "--ignoreos",
        "--ignoresize",
        *rpm_files,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"RPM transaction failed:\n{res.stdout}")

    con = sqlite3.connect(stage_db, isolation_level=None)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.execute("VACUUM")
    con.close()
    os.chmod(stage_db, 0o644)

    os.rename(stage_db, args.output)
    shutil.rmtree(stage_dir)


if __name__ == "__main__":
    main()
