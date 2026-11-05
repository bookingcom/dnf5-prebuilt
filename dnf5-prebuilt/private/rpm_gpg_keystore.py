#!/usr/bin/env python3
"""rpm_gpg_keystore: creates a hermetic GPG keystore directory for dnf5/rpm."""

import argparse
import os
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description="Create RPM GPG keystore directory")
    parser.add_argument("--output", required=True, help="Output directory for keystore")
    parser.add_argument("--rpmdb", help="Optional source rpmdb.sqlite file")
    parser.add_argument("--key", action="append", default=[], help="GPG public key file(s)")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if args.rpmdb and os.path.exists(args.rpmdb):
        target_db = os.path.join(args.output, "rpmdb.sqlite")
        shutil.copyfile(args.rpmdb, target_db)
        os.chmod(target_db, 0o644)

    pubkeys_dir = os.path.join(args.output, "pubkeys")
    if args.key:
        os.makedirs(pubkeys_dir, exist_ok=True)
        for idx, key_path in enumerate(args.key):
            if not os.path.exists(key_path):
                continue
            base = os.path.basename(key_path)
            stem = base.rsplit(".", 1)[0] if "." in base else base
            dest_name = f"{stem}_{idx}.key"
            shutil.copyfile(key_path, os.path.join(pubkeys_dir, dest_name))

    # Touch .keyring.lock to prevent rpm from trying to create it at runtime
    lock_path = os.path.join(args.output, ".keyring.lock")
    with open(lock_path, "a"):
        pass


if __name__ == "__main__":
    main()
