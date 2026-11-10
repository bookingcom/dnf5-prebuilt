#!/usr/bin/env python3
"""rpm_extract: extracts requested files and directories from RPM packages using bsdtar."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def normalize_path(p: str) -> str:
    """Canonicalizes a path by removing leading './' or '/' and trailing '/'."""
    p = p.strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/").rstrip("/")


def extract_entry_from_rpms(entry_rel: str, tree_root: str, rpm_data: list, bsdtar: str) -> bool:
    """Extracts an entry (file, symlink, or directory contents) from RPMs into tree_root.

    Searches RPMs in reverse order (to prefer latest package).
    """
    norm = normalize_path(entry_rel)
    for rpm_path, entries in reversed(rpm_data):
        if norm in entries:
            res = subprocess.run(
                [bsdtar, "-xf", rpm_path, "-C", tree_root, entries[norm]],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return True
        # Check if norm is a directory with entries
        dir_entries = [orig for n, orig in entries.items() if n == norm or n.startswith(norm + "/")]
        if dir_entries:
            res = subprocess.run(
                [bsdtar, "-xf", rpm_path, "-C", tree_root] + dir_entries,
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return True
    return False


def resolve_path_in_tree(
    tree_root: str,
    path_rel: str,
    rpm_data: list,
    bsdtar: str,
    max_depth: int = 40,
) -> str:
    """Resolves path_rel inside tree_root, extracting any missing targets or intermediate symlinks.

    Clamps relative symlinks escaping root ('..') at tree_root and resolves absolute
    symlinks relative to tree_root.
    """
    components = [c for c in normalize_path(path_rel).split("/") if c and c != "."]
    resolved_parts = []
    depth = 0

    while components:
        comp = components.pop(0)
        depth += 1
        if depth > max_depth:
            sys.stderr.write(f"Error: symlink cycle or recursion depth exceeded resolving '{path_rel}'.\n")
            sys.exit(1)

        if comp == "..":
            if resolved_parts:
                resolved_parts.pop()
            # else clamped at tree_root
            continue

        resolved_parts.append(comp)
        curr_rel = "/".join(resolved_parts)
        curr_full = os.path.join(tree_root, curr_rel)

        if not os.path.lexists(curr_full):
            extract_entry_from_rpms(curr_rel, tree_root, rpm_data, bsdtar)

        if os.path.islink(curr_full):
            target = os.readlink(curr_full)
            if os.path.isabs(target):
                components = [c for c in target.split("/") if c and c != "."] + components
                resolved_parts = []
            else:
                resolved_parts.pop()
                components = [c for c in target.split("/") if c and c != "."] + components

    final_rel = "/".join(resolved_parts)
    final_full = os.path.join(tree_root, final_rel)
    if not os.path.lexists(final_full):
        if not extract_entry_from_rpms(final_rel, tree_root, rpm_data, bsdtar):
            sys.stderr.write(
                f"Error: symlink target '{final_rel}' (resolving '{path_rel}') not found in any RPM.\n"
            )
            sys.exit(1)

    return final_rel


def copy_dir_dereferencing(
    tree_root: str,
    curr_rel: str,
    dest_dir: str,
    rpm_data: list,
    bsdtar: str,
    visited_dirs: set,
):
    """Recursively copies curr_rel to dest_dir, dereferencing all symlinks within tree_root."""
    resolved_rel = resolve_path_in_tree(tree_root, curr_rel, rpm_data, bsdtar)
    resolved_full = os.path.join(tree_root, resolved_rel)

    if os.path.isdir(resolved_full):
        if resolved_rel in visited_dirs:
            sys.stderr.write(f"Error: circular directory reference detected at '{curr_rel}' -> '{resolved_rel}'.\n")
            sys.exit(1)
        visited_dirs = visited_dirs | {resolved_rel}
        os.makedirs(dest_dir, exist_ok=True)
        for child in sorted(os.listdir(resolved_full)):
            child_rel = f"{resolved_rel}/{child}" if resolved_rel else child
            child_dest = os.path.join(dest_dir, child)
            copy_dir_dereferencing(tree_root, child_rel, child_dest, rpm_data, bsdtar, visited_dirs)
    elif os.path.isfile(resolved_full):
        parent = os.path.dirname(dest_dir)
        if parent:
            os.makedirs(parent, exist_ok=True)
        shutil.copy2(resolved_full, dest_dir)
    else:
        sys.stderr.write(f"Error: unsupported file type at '{curr_rel}' -> '{resolved_rel}'.\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Extract files and directories from RPMs")
    parser.add_argument("--bsdtar", required=True, help="Path to bsdtar binary")
    parser.add_argument("--rpm", action="append", default=[], required=True, help="RPM package file(s) in order")
    parser.add_argument(
        "--file",
        action="append",
        nargs=2,
        default=[],
        metavar=("SRC", "DST"),
        help="Source relative path and destination file path",
    )
    parser.add_argument(
        "--dir",
        action="append",
        nargs=2,
        default=[],
        metavar=("SRC", "DST"),
        help="Source relative path and destination directory path",
    )
    args = parser.parse_args()

    req_files = [(normalize_path(src), dst) for src, dst in args.file if src.strip()]
    req_dirs = [(normalize_path(src), dst) for src, dst in args.dir if src.strip()]

    with tempfile.TemporaryDirectory() as tree_root:
        found_files = set()
        found_dirs = set()
        rpm_data = []

        # List and initial extraction in RPM order (later RPMs overwrite earlier ones)
        for rpm_path in args.rpm:
            if not os.path.exists(rpm_path):
                sys.stderr.write(f"Error: RPM file '{rpm_path}' not found.\n")
                sys.exit(1)

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
            for src_f, _ in req_files:
                if src_f in entries:
                    extract_args.append(entries[src_f])
                    found_files.add(src_f)

            for src_d, _ in req_dirs:
                matching = [orig for norm, orig in entries.items() if norm == src_d or norm.startswith(src_d + "/")]
                if matching:
                    extract_args.extend(matching)
                    found_dirs.add(src_d)

            if extract_args:
                # Deduplicate while preserving order
                seen_args = set()
                dedup_args = []
                for a in extract_args:
                    if a not in seen_args:
                        seen_args.add(a)
                        dedup_args.append(a)

                extract_res = subprocess.run(
                    [args.bsdtar, "-xf", rpm_path, "-C", tree_root] + dedup_args,
                    capture_output=True,
                    text=True,
                )
                if extract_res.returncode != 0:
                    sys.stderr.write(f"Error extracting files from RPM '{rpm_path}':\n{extract_res.stderr}\n")
                    sys.exit(extract_res.returncode)

        # Check for missing files or directories in initial request
        missing_files = [src_f for src_f, _ in req_files if src_f not in found_files]
        missing_dirs = [src_d for src_d, _ in req_dirs if src_d not in found_dirs]
        if missing_files or missing_dirs:
            sys.stderr.write("Error: requested entries were not found in any of the provided RPM packages:\n")
            for f in missing_files:
                sys.stderr.write(f"  - (file) {f}\n")
            for d in missing_dirs:
                sys.stderr.write(f"  - (dir)  {d}\n")
            sys.exit(1)

        # Resolve and dereference requested files
        for src_f, dst_f in req_files:
            resolved_rel = resolve_path_in_tree(tree_root, src_f, rpm_data, args.bsdtar)
            resolved_full = os.path.join(tree_root, resolved_rel)
            if not os.path.isfile(resolved_full):
                sys.stderr.write(f"Error: '{src_f}' resolved to '{resolved_rel}' which is not a regular file.\n")
                sys.exit(1)
            dst_parent = os.path.dirname(dst_f)
            if dst_parent:
                os.makedirs(dst_parent, exist_ok=True)
            shutil.copy2(resolved_full, dst_f)

        # Resolve and dereference requested directories
        for src_d, dst_d in req_dirs:
            copy_dir_dereferencing(tree_root, src_d, dst_d, rpm_data, args.bsdtar, set())


if __name__ == "__main__":
    main()
