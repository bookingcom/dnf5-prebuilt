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

    for pkg in packages:
        name = pkg.get("name")
        version = pkg.get("version")
        arch = pkg.get("arch")
        url = pkg.get("url")
        integrity = pkg.get("integrity")
        checksum = pkg.get("checksum")

        if not name or not isinstance(name, str):
            raise ValueError(f"{path}: invalid or missing 'name': {pkg}")
        if not version or not isinstance(version, str):
            raise ValueError(f"{path}: invalid or missing 'version': {pkg}")
        if not arch or not isinstance(arch, str):
            raise ValueError(f"{path}: invalid or missing 'arch': {pkg}")
        if not url or not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"{path}: invalid or missing 'url': {pkg}")
        if not integrity or not isinstance(integrity, str):
            raise ValueError(f"{path}: invalid or missing 'integrity': {pkg}")
        if not (integrity.startswith("sha256-") or len(integrity) == 64):
            raise ValueError(f"{path}: integrity is neither SRI sha256- nor 64-char hex: {integrity}")
        if not checksum or not isinstance(checksum, str) or len(checksum) != 64:
            raise ValueError(f"{path}: invalid or missing 64-char sha256 checksum: {pkg}")

        print(f"  OK: {name}-{version}.{arch} -> {url} (integrity: {integrity}, sha256: {checksum[:8]}...)")

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
