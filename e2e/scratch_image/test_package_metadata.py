#!/usr/bin/env python3
"""Validates generated supply-chain package_metadata and integrity attributes."""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Validate package_metadata JSON files")
    parser.add_argument(
        "--check",
        action="append",
        nargs=4,
        metavar=("NAME", "METADATA_FILE", "INTEGRITY_FILE", "EXPECTED_PURL"),
        help="Check a package metadata target: name, metadata file, integrity file, expected purl",
    )
    args = parser.parse_args()

    for name, metadata_path, integrity_path, expected_purl in args.check:
        print(f"Checking package_metadata for {name}...")
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert "label" in meta, f"Missing label in {metadata_path}"
        assert "purl" in meta, f"Missing purl in {metadata_path}"
        assert meta["purl"] == expected_purl, (
            f"PURL mismatch for {name}: expected {expected_purl}, got {meta['purl']}"
        )

        assert "attributes" in meta, f"Missing attributes in {metadata_path}"
        attrs = meta["attributes"]
        assert "build.bazel.attribute.integrity" in attrs, (
            f"Missing integrity attribute in {metadata_path}"
        )

        with open(integrity_path, "r", encoding="utf-8") as f:
            integrity_data = json.load(f)

        assert isinstance(integrity_data, list), f"Expected list in {integrity_path}"
        assert len(integrity_data) >= 1, f"Empty integrity list in {integrity_path}"
        assert integrity_data[0].startswith("sha256-"), (
            f"Invalid SRI format in {integrity_path}: {integrity_data[0]}"
        )
        print(f"  OK: {name} -> PURL: {meta['purl']}, SRI: {integrity_data[0]}")

    print("All package_metadata checks passed successfully!")


if __name__ == "__main__":
    main()
