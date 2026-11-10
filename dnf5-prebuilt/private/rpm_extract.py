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
    rpm_data = []

    for rpm_path in args.rpm:
        if not os.path.exists(rpm_path):
            sys.stderr.write(f"Error: RPM file '{rpm_path}' not found.\n")
            sys.exit(1)

        # List contents of RPM using bsdtar -tf
        list_res = subprocess.run([args.bsdtar, "-tf", rpm_path], capture_output=True, text=True)
        if list_res.returncode != 0:
            sys.stderr.write(f"Error listing contents of RPM '{rpm_path}':\n{list_res.stderr}\n")
            sys.exit(list_res.returncode)

        entries = {}
        for line in list_res.stdout.splitlines():
            orig = line.strip()
            norm = normalize_path(orig)
            if norm:
                entries[norm] = orig

        rpm_data.append((rpm_path, entries))

        extract_args = []
        for f in req_files:
            if f in entries:
                extract_args.append(entries[f])
                found_files.add(f)

        for d in req_dirs:
            matching = [orig for norm, orig in entries.items() if norm == d or norm.startswith(d + "/")]
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

    # Follow and extract any symlink targets across all provided RPMs so symlinks can be dereferenced
    out_dir_abs = os.path.abspath(args.output_dir)
    for f in req_files:
        full_path = os.path.join(args.output_dir, f)
        visited = set()
        while os.path.islink(full_path):
            if full_path in visited:
                sys.stderr.write(f"Error: circular symlink detected for '{f}'\n")
                sys.exit(1)
            visited.add(full_path)

            target = os.readlink(full_path)
            if os.path.isabs(target):
                norm_target = normalize_path(target)
            else:
                rel_dir = os.path.dirname(full_path)
                abs_target = os.path.normpath(os.path.join(rel_dir, target))
                abs_target_norm = os.path.abspath(abs_target)
                if abs_target_norm.startswith(out_dir_abs + os.sep):
                    norm_target = normalize_path(abs_target_norm[len(out_dir_abs) + 1:])
                else:
                    norm_target = normalize_path(abs_target)

            target_on_disk = os.path.join(args.output_dir, norm_target)
            if not os.path.lexists(target_on_disk):
                # Search all RPMs in reverse order (to prefer latest package version)
                extracted_target = False
                for rpm_path, entries in reversed(rpm_data):
                    if norm_target in entries:
                        res = subprocess.run(
                            [args.bsdtar, "-xf", rpm_path, "-C", args.output_dir, entries[norm_target]],
                            capture_output=True,
                            text=True,
                        )
                        if res.returncode == 0:
                            extracted_target = True
                            break
                if not extracted_target:
                    sys.stderr.write(
                        f"Warning: symlink target '{norm_target}' for '{f}' could not be extracted from RPMs.\n"
                    )
                    break

            full_path = target_on_disk

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
