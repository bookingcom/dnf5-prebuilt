#!/usr/bin/env python3
"""rpm_extract_entry: copies an extracted file or directory to its declared target location."""

import argparse
import os
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description="Copy extracted entry to target destination")
    parser.add_argument("--src", required=True, help="Path to source entry inside extracted tree")
    parser.add_argument("--dst", required=True, help="Destination target path")
    parser.add_argument("--is-dir", action="store_true", help="Whether entry is a directory")
    args = parser.parse_args()

    if not os.path.lexists(args.src):
        sys.stderr.write(f"Error: source entry '{args.src}' does not exist in extracted tree.\n")
        sys.exit(1)

    if args.is_dir:
        os.makedirs(args.dst, exist_ok=True)
        shutil.copytree(args.src, args.dst, symlinks=True, dirs_exist_ok=True)
    else:
        parent = os.path.dirname(os.path.abspath(args.dst))
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.islink(args.src):
            target = os.readlink(args.src)
            src_dir = os.path.dirname(args.src)
            abs_target = os.path.normpath(os.path.join(src_dir, target))
            if os.path.lexists(abs_target):
                # Copy the actual target contents to avoid dangling symlinks
                shutil.copy2(abs_target, args.dst)
            else:
                shutil.copy2(args.src, args.dst)
        else:
            shutil.copy2(args.src, args.dst)


if __name__ == "__main__":
    main()
