#!/usr/bin/env python3
"""rpm_script: extracts pre or post installation scriptlets from an RPM package using rpm."""

import argparse
import os
import subprocess
import sys


def extract_script(rpm_bin: str, rpm_path: str, script_type: str) -> bytes:
    """Extracts pre- or post-install scriptlet from an RPM using rpm queryformat."""
    tag = "PREIN" if script_type == "pre" else "POSTIN"
    cmd = [
        rpm_bin,
        "-qp",
        "--nosignature",
        "--nodigest",
        "--queryformat",
        f"[%{{{tag}}}]",
        rpm_path,
    ]
    env = os.environ.copy()
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        sys.stderr.write(
            f"rpm query failed (exit {proc.returncode}): {proc.stderr.decode('utf-8', errors='replace')}\n"
        )
        sys.exit(proc.returncode)
    return proc.stdout


def main():
    parser = argparse.ArgumentParser(description="Extract scriptlets from RPM packages using rpm.")
    parser.add_argument("--rpm-bin", required=True, help="Path to rpm binary")
    parser.add_argument("--rpm", required=True, help="Path to RPM file")
    parser.add_argument("--script", choices=["pre", "post"], required=True, help="Script type to extract")
    parser.add_argument("--output", required=True, help="Path to output script file")
    args = parser.parse_args()

    content = extract_script(args.rpm_bin, args.rpm, args.script)
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(content)


if __name__ == "__main__":
    main()
