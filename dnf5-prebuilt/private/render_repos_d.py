#!/usr/bin/env python3
"""render_repos_d: renders repos.d directory from individual .repo files and directory artifacts."""

import argparse
import os
import sys


def process_repo_file(src_path: str, dst_path: str):
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("@REPO_DIR@", "${repo_dir}")
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Render repos.d directory")
    parser.add_argument("--output", required=True, help="Destination directory for repos.d")
    parser.add_argument("--file", action="append", default=[], help="Individual .repo file")
    parser.add_argument("--dir", action="append", default=[], help="Directory artifact containing .repo files")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    seen = set()

    for file_path in args.file:
        if not os.path.exists(file_path):
            sys.stderr.write(f"Error: repo config file '{file_path}' does not exist\n")
            sys.exit(1)
        base = os.path.basename(file_path)
        stem = base.rsplit(".", 1)[0]
        if stem in seen:
            sys.stderr.write(f"Error: repo_configs: duplicate repository definition for '{stem}'\n")
            sys.exit(1)
        seen.add(stem)
        dest = os.path.join(args.output, f"{stem}.repo")
        process_repo_file(file_path, dest)

    for dir_path in args.dir:
        if not os.path.exists(dir_path):
            sys.stderr.write(f"Error: repo config directory '{dir_path}' does not exist\n")
            sys.exit(1)
        for root, _, files in os.walk(dir_path):
            for file_name in sorted(files):
                if file_name.endswith(".repo"):
                    stem = file_name.rsplit(".", 1)[0]
                    if stem in seen:
                        sys.stderr.write(f"Error: repo_configs: duplicate repository definition for '{stem}'\n")
                        sys.exit(1)
                    seen.add(stem)
                    src = os.path.join(root, file_name)
                    dest = os.path.join(args.output, f"{stem}.repo")
                    process_repo_file(src, dest)


if __name__ == "__main__":
    main()
