#!/usr/bin/env python3
"""Integration test verifying rpm_layer archives contain no entries with symlinked parents."""

import os
import sys
import tarfile


def normalize_entry_name(name: str) -> str:
    while name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


def validate_layer_tar(tar_path: str) -> None:
    print(f"Validating layer archive: {tar_path}")
    if not os.path.exists(tar_path):
        raise FileNotFoundError(f"Tar archive not found: {tar_path}")

    with tarfile.open(tar_path, "r:") as t:
        members = t.getmembers()
        symlinks = {}
        for m in members:
            norm = normalize_entry_name(m.name)
            if m.issym() and norm:
                symlinks[norm] = m.linkname

        # 1. Assert no entry has a parent directory that is a symlink
        violations = []
        for m in members:
            norm = normalize_entry_name(m.name)
            parts = norm.split("/")
            for j in range(1, len(parts)):
                parent_prefix = "/".join(parts[:j])
                if parent_prefix in symlinks:
                    violations.append(
                        f"Entry '{norm}' has parent '{parent_prefix}' which is a symlink to '{symlinks[parent_prefix]}'"
                    )

        if violations:
            msg = f"Found {len(violations)} entries with symlinked parents in {tar_path}:\n" + "\n".join(violations[:10])
            raise AssertionError(msg)

        # 2. Assert top-level usr-merge symlinks exist
        for sym_name, expected_target in [
            ("bin", "usr/bin"),
            ("lib", "usr/lib"),
            ("lib64", "usr/lib64"),
            ("sbin", "usr/sbin"),
        ]:
            if sym_name not in symlinks:
                raise AssertionError(f"Expected top-level symlink '{sym_name}' not found in {tar_path}")
            if symlinks[sym_name] != expected_target:
                raise AssertionError(
                    f"Symlink '{sym_name}' points to '{symlinks[sym_name]}', expected '{expected_target}'"
                )

        # 3. Assert libgcc entries are properly canonicalized under usr/lib64
        member_names = {normalize_entry_name(m.name) for m in members}
        for bad_prefix in ("lib64/", "bin/", "sbin/", "lib/"):
            bad_entries = [name for name in member_names if name.startswith(bad_prefix)]
            if bad_entries:
                raise AssertionError(
                    f"Found entries under symlinked prefix '{bad_prefix}' in {tar_path}: {bad_entries[:5]}"
                )

        libgcc_entries = [name for name in member_names if "libgcc_s" in name]
        if not libgcc_entries:
            raise AssertionError(f"Expected libgcc_s entries in {tar_path}, none found")

        for entry in libgcc_entries:
            if not entry.startswith("usr/lib64/"):
                raise AssertionError(f"libgcc entry '{entry}' not under usr/lib64/ in {tar_path}")

        print(f"PASS: {tar_path} verified ({len(members)} entries, 0 with symlinked parents, libgcc properly located)")


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <tar_path> [<tar_path>...]", file=sys.stderr)
        return 1

    for path in sys.argv[1:]:
        validate_layer_tar(path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
