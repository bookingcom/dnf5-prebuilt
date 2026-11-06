#!/usr/bin/env python3
"""rpm_merge: orders RPM packages using a lockfile and merges them using bsdtar."""

import argparse
import json
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Merge RPMs with bsdtar in topological install order")
    parser.add_argument("--bsdtar", required=True, help="Path to bsdtar binary")
    parser.add_argument("--out", required=True, help="Path to output tar file")
    parser.add_argument("--lockfile", help="Path to lockfile JSON")
    parser.add_argument("--rpm-bin", help="Path to rpm binary")
    parser.add_argument("--rpm", dest="rpms", action="append", default=[], help="RPM package paths")
    return parser.parse_args()


def load_lockfile_order(lockfile_path):
    if not lockfile_path or not os.path.isfile(lockfile_path):
        return [], {}
    with open(lockfile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    install_order = data.get("install_order") or data.get("order")
    packages = data.get("packages", [])
    if not install_order and packages:
        install_order = [p["name"] for p in packages if "name" in p]

    packages_map = {}
    for p in packages:
        name = p.get("name")
        if not name:
            continue
        packages_map[name] = p

    return install_order or [], packages_map


def match_rpm_to_package(rpm_path, packages_map, rpm_bin=None):
    base = os.path.basename(rpm_path)

    # 1. Exact match with url basename
    for name, p in packages_map.items():
        url = p.get("url", "")
        if url and os.path.basename(url) == base:
            return name

    # 2. Exact match with nevra
    for name, p in packages_map.items():
        nevra = p.get("nevra", "")
        if nevra and (base == f"{nevra}.rpm" or base == nevra):
            return name

    # 3. Check name prefix: e.g. base == "curl-8.12.1-..." starts with "curl-"
    for name in packages_map:
        if base.startswith(f"{name}-") or base == name or base == f"{name}.rpm":
            return name

    # 4. Fallback to querying the RPM package header directly
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
    args = parse_args()

    rpms = args.rpms
    if args.lockfile:
        install_order, packages_map = load_lockfile_order(args.lockfile)
        if install_order:
            order_indices = {name: i for i, name in enumerate(install_order)}

            def sort_key(rpm_p):
                pkg_name = match_rpm_to_package(rpm_p, packages_map, args.rpm_bin)
                if pkg_name and pkg_name in order_indices:
                    return (order_indices[pkg_name], rpm_p)
                return (len(install_order) + 1, rpm_p)

            rpms = sorted(rpms, key=sort_key)

    cmd = [
        args.bsdtar,
        "-cf", args.out,
        "--format=pax",
        "--numeric-owner",
        "--owner=0",
        "--group=0",
    ] + [f"@{p}" for p in rpms]

    res = subprocess.run(cmd)
    if res.returncode != 0:
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
