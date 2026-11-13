#!/usr/bin/env python3
"""Validates that extracted RPM scriptlets contain expected content."""

import argparse
import os
import sys

EXPECTED_SUBSTRINGS = {
    "setup:post-script": "os.remove(\"/etc/\"..name..\".rpmnew\")",
    "bash:post-script": "/etc/shells",
    "glibc:pre-script": "Check that the running kernel is new enough",
    "glibc:post-script": "call_ldconfig()",
}


def main():
    parser = argparse.ArgumentParser(description="Validate extracted RPM scripts")
    parser.add_argument(
        "--script",
        action="append",
        nargs=2,
        metavar=("NAME", "PATH"),
        required=True,
        help="Pair of script name (e.g. setup:post-script) and file path",
    )
    args = parser.parse_args()

    for name, path in args.script:
        if not os.path.exists(path):
            sys.stderr.write(f"Error: script file does not exist: {path}\n")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            sys.stderr.write(f"Error: script file is empty: {path}\n")
            sys.exit(1)
        if name in EXPECTED_SUBSTRINGS:
            expected = EXPECTED_SUBSTRINGS[name]
            if expected not in content:
                sys.stderr.write(f"Error: expected '{expected}' in {name} ({path})\n")
                sys.exit(1)
        print(f"OK: {name} ({len(content)} bytes)")

    print("All extracted scripts validated successfully.")


if __name__ == "__main__":
    main()
