#!/usr/bin/env python3
"""rpm_gpg_verify: verifies an RPM package signature against a GPG keystore."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description="Verify RPM signature against keystore")
    parser.add_argument("--rpm-bin", required=True, help="Path to rpm binary")
    parser.add_argument("--keystore", required=True, help="Path to keystore directory")
    parser.add_argument("--rpm", required=True, help="Path to RPM package file")
    parser.add_argument("--output", required=True, help="Output marker file")
    args = parser.parse_args()

    keystore_src = os.path.abspath(args.keystore)
    rpm_file = os.path.abspath(args.rpm)
    rpm_bin = os.path.abspath(args.rpm_bin)

    with tempfile.TemporaryDirectory() as tmp_dir:
        keystore_dir = os.path.join(tmp_dir, "keystore")
        shutil.copytree(keystore_src, keystore_dir)

        lock_path = os.path.join(keystore_dir, ".keyring.lock")
        if not os.path.exists(lock_path):
            with open(lock_path, "a"):
                pass

        cmd = [
            rpm_bin,
            "--dbpath", keystore_dir,
            "--install", "--test",
            "--nodeps", "--noscripts",
            "--ignorearch", "--ignoreos",
            "--ignoresize",
            "--replacefiles", "--replacepkgs",
        ]

        has_rpmdb = os.path.isfile(os.path.join(keystore_dir, "rpmdb.sqlite"))
        has_pubkeys = os.path.isdir(os.path.join(keystore_dir, "pubkeys")) and bool(
            os.listdir(os.path.join(keystore_dir, "pubkeys"))
        )

        if has_pubkeys and not has_rpmdb:
            cmd.extend(["--define", "_keyring fs"])

        cmd.append(rpm_file)

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if res.returncode != 0:
            # If both rpmdb and pubkeys exist and default failed, try _keyring fs
            if has_rpmdb and has_pubkeys:
                cmd_fs = [
                    rpm_bin,
                    "--define", "_keyring fs",
                    "--dbpath", keystore_dir,
                    "--install", "--test",
                    "--nodeps", "--noscripts",
                    "--ignorearch", "--ignoreos",
                    "--ignoresize",
                    "--replacefiles", "--replacepkgs",
                    rpm_file,
                ]
                res_fs = subprocess.run(cmd_fs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                if res_fs.returncode == 0:
                    res = res_fs

        if res.returncode != 0:
            sys.stderr.write(f"GPG signature verification failed for {args.rpm}:\n{res.stdout}\n")
            sys.exit(res.returncode)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("OK\n")


if __name__ == "__main__":
    main()
