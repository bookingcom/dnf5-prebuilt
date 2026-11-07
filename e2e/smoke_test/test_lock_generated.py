#!/usr/bin/env python3
"""Validates that generated RPM lock files contain valid package entries with URLs and sha256 integrity."""

import argparse
import json
import sys


def validate_lock_file(path: str) -> None:
    print(f"Validating lock file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object at top level")

    packages = data.get("packages")
    if not isinstance(packages, list) or len(packages) == 0:
        raise ValueError(f"{path}: expected non-empty 'packages' list")

    install_order = data.get("install_order")
    if not isinstance(install_order, list) or len(install_order) != len(packages):
        raise ValueError(f"{path}: expected valid 'install_order' array matching package count: {install_order}")

    pkg_names = set()
    for pkg in packages:
        name = pkg.get("name")
        version = pkg.get("version")
        arch = pkg.get("arch")
        url = pkg.get("url")
        integrity = pkg.get("integrity")

        if not name or not isinstance(name, str):
            raise ValueError(f"{path}: invalid or missing 'name': {pkg}")
        pkg_names.add(name)
        if not version or not isinstance(version, str):
            raise ValueError(f"{path}: invalid or missing 'version': {pkg}")
        if not arch or not isinstance(arch, str):
            raise ValueError(f"{path}: invalid or missing 'arch': {pkg}")
        if not url or not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
            raise ValueError(f"{path}: invalid or missing 'url': {pkg}")
        if not integrity or not isinstance(integrity, str):
            raise ValueError(f"{path}: invalid or missing 'integrity': {pkg}")
        if not integrity.startswith("sha256-"):
            raise ValueError(f"{path}: integrity is not SRI sha256-: {integrity}")

        print(f"  OK: {name}-{version}.{arch} -> {url} (integrity: {integrity})")

    for order_name in install_order:
        if order_name not in pkg_names:
            raise ValueError(f"{path}: install_order package {order_name} not found in packages list")
    print(f"  Install order: {' -> '.join(install_order)}")

    print(f"Successfully validated {len(packages)} packages in {path}.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated RPM lock files.")
    parser.add_argument("lock_files", nargs="+", help="Paths to lock files to validate")
    args = parser.parse_args()

    for lock_file in args.lock_files:
        validate_lock_file(lock_file)

    print("All lock files validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
