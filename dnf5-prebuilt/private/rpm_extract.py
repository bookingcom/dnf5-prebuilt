#!/usr/bin/env python3
"""rpm_extract: extracts requested files and directories from RPM packages using bsdtar."""

import argparse
import os
import subprocess
import sys


def normalize_path(p: str) -> str:
    """Canonicalizes a path by removing leading './' or '/' and trailing '/'."""
    p = p.strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/").rstrip("/")


def main():
    parser = argparse.ArgumentParser(description="Extract files and directories from RPMs")
    parser.add_argument("--bsdtar", required=True, help="Path to bsdtar binary")
    parser.add_argument("--output-dir", required=True, help="Destination directory for extracted tree")
    parser.add_argument("--rpm", action="append", default=[], help="RPM package file(s) in order")
    parser.add_argument("--file", action="append", default=[], help="File path(s) to extract")
    parser.add_argument("--dir", action="append", default=[], help="Directory path(s) to extract")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    req_files = [normalize_path(f) for f in args.file if f.strip()]
    req_dirs = [normalize_path(d) for d in args.dir if d.strip()]

    found_files = set()
    found_dirs = set()

    for rpm_path in args.rpm:
        if not os.path.exists(rpm_path):
            sys.stderr.write(f"Error: RPM file '{rpm_path}' not found.\n")
            sys.exit(1)

        # List contents of RPM using bsdtar -tf
        list_res = subprocess.run([args.bsdtar, "-tf", rpm_path], capture_output=True, text=True)
        if list_res.returncode != 0:
            sys.stderr.write(f"Error listing contents of RPM '{rpm_path}':\n{list_res.stderr}\n")
            sys.exit(list_res.returncode)

        rpm_entries = {}
        for line in list_res.stdout.splitlines():
            orig = line.strip()
            norm = normalize_path(orig)
            if norm:
                rpm_entries[norm] = orig

        extract_args = []
        for f in req_files:
            if f in rpm_entries:
                extract_args.append(rpm_entries[f])
                found_files.add(f)

        for d in req_dirs:
            matching = [orig for norm, orig in rpm_entries.items() if norm == d or norm.startswith(d + "/")]
            if matching:
                extract_args.extend(matching)
                found_dirs.add(d)

        if extract_args:
            # Deduplicate extract_args while preserving order
            seen_args = set()
            dedup_args = []
            for a in extract_args:
                if a not in seen_args:
                    seen_args.add(a)
                    dedup_args.append(a)

            extract_res = subprocess.run(
                [args.bsdtar, "-xf", rpm_path, "-C", args.output_dir] + dedup_args,
                capture_output=True,
                text=True,
            )
            if extract_res.returncode != 0:
                sys.stderr.write(f"Error extracting files from RPM '{rpm_path}':\n{extract_res.stderr}\n")
                sys.exit(extract_res.returncode)

            # Auto-extract relative symlink targets within this RPM if any
            for f in req_files:
                extracted_f = os.path.join(args.output_dir, f)
                if os.path.islink(extracted_f):
                    target = os.readlink(extracted_f)
                    if not os.path.isabs(target):
                        resolved = normalize_path(os.path.normpath(os.path.join(os.path.dirname(f), target)))
                        if resolved in rpm_entries and not os.path.lexists(os.path.join(args.output_dir, resolved)):
                            subprocess.run(
                                [args.bsdtar, "-xf", rpm_path, "-C", args.output_dir, rpm_entries[resolved]],
                                check=False,
                            )

    # Check for missing files or directories
    missing_files = [f for f in req_files if f not in found_files]
    missing_dirs = [d for d in req_dirs if d not in found_dirs]

    if missing_files or missing_dirs:
        sys.stderr.write("Error: requested entries were not found in any of the provided RPM packages:\n")
        for f in missing_files:
            sys.stderr.write(f"  - (file) {f}\n")
        for d in missing_dirs:
            sys.stderr.write(f"  - (dir)  {d}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
