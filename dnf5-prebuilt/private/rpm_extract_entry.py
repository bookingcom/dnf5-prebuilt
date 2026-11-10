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

        # Dereference symlinks: follow the symlink chain to the real target file
        real_src = os.path.realpath(args.src)
        if not os.path.exists(real_src):
            sys.stderr.write(
                f"Error: file '{args.src}' is a symlink resolving to non-existent target '{real_src}'.\n"
            )
            sys.exit(1)
        if os.path.isdir(real_src):
            sys.stderr.write(f"Error: file '{args.src}' resolves to a directory '{real_src}'.\n")
            sys.exit(1)

        if os.path.lexists(args.dst):
            os.remove(args.dst)

        # Copy the dereferenced file content and mode
        shutil.copy2(real_src, args.dst, follow_symlinks=True)

        if os.path.islink(args.dst):
            sys.stderr.write(f"Error: failed to dereference '{args.dst}', output is still a symlink.\n")
            sys.exit(1)


if __name__ == "__main__":
    main()
