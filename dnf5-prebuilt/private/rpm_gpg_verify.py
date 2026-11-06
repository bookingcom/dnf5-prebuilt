#!/usr/bin/env python3
"""rpm_gpg_verify: verifies an RPM package signature against an rpmdb."""

import argparse
import os
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description="Verify RPM signature against rpmdb")
    parser.add_argument("--rpm-bin", required=True, help="Path to rpm binary")
    parser.add_argument("--rpmdb", required=True, help="Path to rpmdb directory")
    parser.add_argument("--keyring", choices=["rpmdb", "fs"], default="rpmdb", help="Keyring backend")
    parser.add_argument("--rpm", required=True, help="Path to RPM package file")
    parser.add_argument("--output", required=True, help="Output marker file")
    args = parser.parse_args()

    rpmdb_dir = os.path.abspath(args.rpmdb)
    rpm_file = os.path.abspath(args.rpm)
    rpm_bin = os.path.abspath(args.rpm_bin)

    lock_file = os.path.join(tempfile.gettempdir(), f".rpm_keyring_{os.getpid()}.lock")
    cmd = [
        rpm_bin,
        "--define", f"_keyring {args.keyring}",
        "--define", f"_keyring_lockpath {lock_file}",
        "--dbpath", rpmdb_dir,
        "--install", "--test",
        "--nodeps", "--noscripts",
        "--ignorearch", "--ignoreos",
        "--ignoresize",
        "--replacefiles", "--replacepkgs",
        rpm_file,
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    finally:
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError:
                pass

    if res.returncode != 0:
        sys.stderr.write(f"GPG signature verification failed for {args.rpm}:\n{res.stdout}\n")
        sys.exit(res.returncode)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("OK\n")


if __name__ == "__main__":
    main()
