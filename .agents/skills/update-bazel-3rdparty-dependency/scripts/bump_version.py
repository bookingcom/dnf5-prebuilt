#!/usr/bin/env python3
"""Scaffold a new version of a local registry module in bazel/3rdparty.

Usage:
    python3 .agents/skills/update-bazel-3rdparty-dependency/scripts/bump_version.py <module> <new_version> [options]

Options:
    --from-version <ver>   Existing version to copy overlay/patches from (default: latest in metadata.json)
    --url <url>            New upstream archive URL to set in source.json
    --strip-prefix <pfx>   New strip_prefix for source.json
    --fetch                Download the new URL archive to compute its integrity hash immediately
    --update-root          Automatically update bazel_dep version in root MODULE.bazel
    --dry-run              Print what would be done without making changes

Example:
    python3 .agents/skills/update-bazel-3rdparty-dependency/scripts/bump_version.py popt 1.19.dnf5.2
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys


def find_repo_root() -> str:
    # Use BUILD_WORKSPACE_DIRECTORY if run via bazel run, otherwise traverse up
    env_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if env_root and os.path.isdir(os.path.join(env_root, "bazel", "3rdparty")):
        return env_root

    current = os.path.abspath(os.getcwd())
    while current != os.path.dirname(current):
        if os.path.isdir(os.path.join(current, "bazel", "3rdparty")):
            return current
        current = os.path.dirname(current)
    raise RuntimeError("Could not find repository root containing bazel/3rdparty")


def update_module_file(path: str, module_name: str, new_version: str, dry_run: bool = False):
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match module(name = "...", version = "...")
    pattern = rf'(module\s*\(\s*name\s*=\s*["\']{re.escape(module_name)}["\']\s*,\s*version\s*=\s*["\'])[^"\']+(["\'])'
    new_content = re.sub(pattern, rf'\g<1>{new_version}\g<2>', content)

    if new_content == content:
        # Try multiline module(
        pattern_multi = rf'(module\s*\([^)]*name\s*=\s*["\']{re.escape(module_name)}["\'][^)]*version\s*=\s*["\'])[^"\']+(["\'])'
        new_content = re.sub(pattern_multi, rf'\g<1>{new_version}\g<2>', content, flags=re.DOTALL)

    if not dry_run and new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)


def update_root_module(repo_root: str, module_name: str, new_version: str, dry_run: bool = False) -> bool:
    root_module_path = os.path.join(repo_root, "MODULE.bazel")
    if not os.path.isfile(root_module_path):
        return False

    with open(root_module_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match bazel_dep(name = "<module>", version = "<old>")
    dep_pattern = rf'(bazel_dep\s*\(\s*name\s*=\s*["\']{re.escape(module_name)}["\']\s*,\s*version\s*=\s*["\'])[^"\']+(["\'])'
    new_content = re.sub(dep_pattern, rf'\g<1>{new_version}\g<2>', content)

    # Match single_version_override(module_name = "<module>", version = "<old>")
    override_pattern = rf'(single_version_override\s*\(\s*module_name\s*=\s*["\']{re.escape(module_name)}["\']\s*,\s*version\s*=\s*["\'])[^"\']+(["\'])'
    new_content = re.sub(override_pattern, rf'\g<1>{new_version}\g<2>', new_content)

    if new_content != content:
        if not dry_run:
            with open(root_module_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("module", help="Name of the module in bazel/3rdparty/modules")
    parser.add_argument("new_version", help="New version to create (e.g. 1.19.dnf5.2 or 2.16.0)")
    parser.add_argument("--from-version", help="Source version to copy from (default: latest in metadata.json)")
    parser.add_argument("--url", help="New upstream source archive URL")
    parser.add_argument("--strip-prefix", help="New strip_prefix for source.json")
    parser.add_argument("--fetch", action="store_true", help="Download archive to calculate integrity")
    parser.add_argument("--update-root", action="store_true", help="Automatically update root MODULE.bazel")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying files")

    args = parser.parse_args()

    repo_root = find_repo_root()
    registry_modules = os.path.join(repo_root, "bazel", "3rdparty", "modules")
    module_dir = os.path.join(registry_modules, args.module)

    if not os.path.isdir(module_dir):
        print(f"Error: Module '{args.module}' not found under bazel/3rdparty/modules", file=sys.stderr)
        sys.exit(1)

    metadata_path = os.path.join(module_dir, "metadata.json")
    if not os.path.isfile(metadata_path):
        print(f"Error: metadata.json missing for module '{args.module}'", file=sys.stderr)
        sys.exit(1)

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    versions = metadata.get("versions", [])
    if args.new_version in versions:
        print(f"Error: Version '{args.new_version}' already exists in metadata.json. Committed versions are immutable.", file=sys.stderr)
        sys.exit(1)

    from_version = args.from_version or (versions[-1] if versions else None)
    if not from_version:
        print(f"Error: No existing versions found in metadata.json to copy from.", file=sys.stderr)
        sys.exit(1)

    src_vdir = os.path.join(module_dir, from_version)
    if not os.path.isdir(src_vdir):
        print(f"Error: Source version directory '{src_vdir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    dst_vdir = os.path.join(module_dir, args.new_version)
    if os.path.exists(dst_vdir):
        print(f"Error: Destination directory '{dst_vdir}' already exists.", file=sys.stderr)
        sys.exit(1)

    print(f"==> Scaffolding {args.module}@{args.new_version} from {from_version}")

    if args.dry_run:
        print(f"[dry-run] Would copy {src_vdir} to {dst_vdir}")
        print(f"[dry-run] Would update metadata.json to include {args.new_version}")
        if args.url:
            print(f"[dry-run] Would update source.json url to {args.url}")
        if args.strip_prefix:
            print(f"[dry-run] Would update source.json strip_prefix to {args.strip_prefix}")
        if args.update_root:
            print(f"[dry-run] Would update root MODULE.bazel")
        return

    # 1. Copy version tree
    shutil.copytree(src_vdir, dst_vdir)

    # 2. Update MODULE.bazel files in dst_vdir
    update_module_file(os.path.join(dst_vdir, "MODULE.bazel"), args.module, args.new_version)
    update_module_file(os.path.join(dst_vdir, "overlay", "MODULE.bazel"), args.module, args.new_version)

    # 3. Update source.json if url / strip_prefix provided
    source_json_path = os.path.join(dst_vdir, "source.json")
    if os.path.isfile(source_json_path):
        with open(source_json_path, "r", encoding="utf-8") as f:
            source_data = json.load(f)
        if args.url:
            source_data["url"] = args.url
        if args.strip_prefix:
            source_data["strip_prefix"] = args.strip_prefix
        with open(source_json_path, "w", encoding="utf-8") as f:
            json.dump(source_data, f, indent=4, sort_keys=True)
            f.write("\n")

    # 4. Update metadata.json
    versions.append(args.new_version)
    metadata["versions"] = versions
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, sort_keys=False)
        f.write("\n")

    # 5. Run update_integrity.py
    integrity_script = os.path.join(repo_root, "bazel", "3rdparty", "update_integrity.py")
    cmd = [sys.executable, integrity_script, args.module, args.new_version]
    if args.fetch:
        cmd.append("--fetch")
    print(f"==> Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    # 6. Update root MODULE.bazel if requested
    if args.update_root:
        updated = update_root_module(repo_root, args.module, args.new_version)
        if updated:
            print(f"==> Updated {args.module} version to {args.new_version} in root MODULE.bazel")
        else:
            print(f"==> Notice: {args.module} was not found in root MODULE.bazel bazel_dep declarations")

    print("\n✓ Successfully scaffolded new version.")
    print("Next steps:")
    print("  1. Review/edit files in:")
    print(f"     bazel/3rdparty/modules/{args.module}/{args.new_version}/")
    print(f"  2. If overlay or patches were edited, run:")
    print(f"     python3 bazel/3rdparty/update_integrity.py {args.module} {args.new_version}")
    print("  3. Bazel caches local registry files. Always run:")
    print("     bazel shutdown")
    print("  4. Verify with smoke tests and builds:")
    print("     INVOCATION_ID=$(uuidgen) && echo \"Invocation ID: ${INVOCATION_ID}\" && bazel test //bazel/tests/... --config=linux_amd64 --invocation_id=${INVOCATION_ID}")


if __name__ == "__main__":
    main()
