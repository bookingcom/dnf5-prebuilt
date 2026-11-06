#!/usr/bin/env python3
"""rpm_mark: records package headers into an rpmdb without installing them, reproducibly."""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess


def match_rpm_to_package(rpm_path, packages_map, rpm_bin=None):
    base = os.path.basename(rpm_path)
    for name, p in packages_map.items():
        url = p.get("url", "")
        if url and os.path.basename(url) == base:
            return name
    for name, p in packages_map.items():
        nevra = p.get("nevra", "")
        if nevra and (base == f"{nevra}.rpm" or base == nevra):
            return name
    for name in packages_map:
        if base.startswith(f"{name}-") or base == name or base == f"{name}.rpm":
            return name
    if rpm_bin and os.path.isfile(rpm_bin) and os.access(rpm_bin, os.X_OK):
        try:
            res = subprocess.run(
                [rpm_bin, "-qp", "--queryformat=%{NAME}", rpm_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                pkg_name = res.stdout.strip()
                if pkg_name in packages_map:
                    return pkg_name
        except Exception:
            pass
    return None


def main():
    parser = argparse.ArgumentParser(description="rpm_mark tool")
    parser.add_argument("--output", dest="output", required=True, help="Target rpmdb.sqlite file")
    parser.add_argument("--base-rpmdb", dest="base_rpmdb", help="Optional base rpmdb.sqlite file to mark packages on top of")
    parser.add_argument("--lockfile", dest="lockfile", help="Optional lockfile JSON with install_order")
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

    if args.lockfile and os.path.isfile(args.lockfile):
        try:
            with open(args.lockfile, "r", encoding="utf-8") as f:
                lock_data = json.load(f)
            install_order = lock_data.get("install_order") or lock_data.get("order")
            packages = lock_data.get("packages", [])
            if not install_order and packages:
                install_order = [p["name"] for p in packages if "name" in p]
            packages_map = {p["name"]: p for p in packages if "name" in p}
            if install_order:
                order_indices = {name: i for i, name in enumerate(install_order)}
                rpm_files.sort(
                    key=lambda p: (
                        order_indices.get(match_rpm_to_package(p, packages_map, rpm_bin), len(install_order) + 1),
                        p,
                    )
                )
        except Exception:
            pass

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
