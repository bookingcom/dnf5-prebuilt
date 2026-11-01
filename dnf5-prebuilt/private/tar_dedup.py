#!/usr/bin/env python3
"""Deduplicates directory and file entries in an uncompressed tar archive."""

import argparse
import sys
import tarfile


def normalize_entry_name(name: str) -> str:
    """Strips leading './' and trailing '/' to obtain a canonical entry name."""
    while name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate entries in a tar archive.")
    parser.add_argument("--input", required=True, help="Path to input uncompressed tar archive")
    parser.add_argument("--output", required=True, help="Path to output deduplicated tar archive")
    args = parser.parse_args()

    seen_dirs = set()
    seen_files = set()

    with tarfile.open(args.input, mode="r:") as src, \
         tarfile.open(args.output, mode="w:") as dst:
        for member in src:
            norm = normalize_entry_name(member.name)

            if not norm or norm == ".":
                if "." in seen_dirs:
                    continue
                seen_dirs.add(".")
                member.name = "."
                dst.addfile(member)
                continue

            if member.isdir():
                if norm in seen_dirs:
                    continue
                seen_dirs.add(norm)
                member.name = norm
                dst.addfile(member)
            else:
                if norm in seen_files:
                    continue
                seen_files.add(norm)
                member.name = norm
                if member.islnk() and member.linkname.startswith("./"):
                    member.linkname = normalize_entry_name(member.linkname)

                if member.isreg():
                    with src.extractfile(member) as f:
                        dst.addfile(member, fileobj=f)
                else:
                    dst.addfile(member)

    return 0


if __name__ == "__main__":
    sys.exit(main())
