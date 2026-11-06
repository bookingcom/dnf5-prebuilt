---
name: update-bazel-3rdparty-dependency
description: >-
  Update, add, or patch third-party C/C++ or Rust dependencies in the local Bazel registry under bazel/3rdparty. Use when upgrading, patching, or adding versions of local registry modules (json-c, libacl, libmodulemd, libpkgmanifest, librepo, libsmartcols, libsolv, popt, rpm, rpm-sequoia, toml11), refreshing SRI integrity hashes, updating root MODULE.bazel, or ensuring Renovate configuration ignores private Bzlmod packages.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# Updating Dependencies in `bazel/3rdparty`

This skill guides you through upgrading, patching, or adding third-party dependencies maintained in the repository's local Bazel registry under `bazel/3rdparty`.

---

## Key Principles

1. **Committed Versions are Immutable**:
   Never modify a committed version in-place. Always bump to a new version directory:
   - For overlay/patch changes on the same upstream source: append or increment the `.dnf5.<n>` suffix (e.g., `1.19.dnf5.1` -> `1.19.dnf5.2`).
   - For upstream upgrades: create the new upstream version directory (e.g., `2.16.0` or `2.16.0.dnf5.1`).
2. **Renovate Bot Separation**:
   Dependencies in `bazel/3rdparty` are NOT available on BCR. Renovate is configured in `.github/renovate.json` to ignore them. If you add a new module to `bazel/3rdparty`, you **must** also add its name to `matchPackageNames` in `.github/renovate.json`.
3. **Mandatory Bazel Invocation Protocol**:
   All Bazel invocations must generate a UUID and pass `--invocation_id=${INVOCATION_ID}`:
   ```bash
   INVOCATION_ID=$(uuidgen) && echo "Invocation ID: ${INVOCATION_ID}" && bazel <cmd> --invocation_id=${INVOCATION_ID} <args>
   ```
4. **Bazel Cache Invalidation**:
   The Bazel server caches local registry files. Always run `bazel shutdown` after changing files in `bazel/3rdparty`.

---

## Workflow Steps

### Step 1: Inspect Module State

List current modules and their versions:
```bash
ls -l bazel/3rdparty/modules/<module>
cat bazel/3rdparty/modules/<module>/metadata.json
```

### Step 2: Scaffold the New Version

Use the helper script to create the new version directory, clone overlays/patches from the previous version, and register the new version in `metadata.json`:

```bash
# Example 1: Bump internal patch revision (e.g. popt 1.19.dnf5.1 -> 1.19.dnf5.2)
python3 .agents/skills/update-bazel-3rdparty-dependency/scripts/bump_version.py popt 1.19.dnf5.2 --update-root

# Example 2: Upgrade upstream version with new source archive
python3 .agents/skills/update-bazel-3rdparty-dependency/scripts/bump_version.py librepo 1.22.0 \
  --url "https://github.com/rpm-software-management/librepo/archive/refs/tags/1.22.0.tar.gz" \
  --strip-prefix "librepo-1.22.0" \
  --fetch \
  --update-root
```

The script will:
- Copy `overlay/` and `patches/` from the previous version.
- Update `MODULE.bazel` in the new version directory.
- Update `source.json` with the new URL / strip prefix (and fetch archive integrity if `--fetch` is passed).
- Update `metadata.json` versions list.
- Run `bazel/3rdparty/update_integrity.py <module> <new_version>`.
- Optionally update `MODULE.bazel` in the workspace root if `--update-root` is given.

### Step 3: Adjust Overlays, Headers, or Patches

Inspect and modify the overlay BUILD definitions or patches in:
`bazel/3rdparty/modules/<module>/<new_version>/overlay/`
`bazel/3rdparty/modules/<module>/<new_version>/patches/`

Important guidelines:
- Consult [Pitfalls & Best Practices](./references/pitfalls.md) for include hygiene, macOS libc++ differences, and glibc 2.28 (AlmaLinux 8) baseline compatibility.
- Ensure all headers generated at configure time (e.g., `config.h`) are kept in a subfolder and accessed via `-iquote`.
- Use `implementation_deps` for private dependencies so generic headers do not leak into downstream consumers.

### Step 4: Recompute Integrity Hashes

Whenever any file in `overlay/` or `patches/` is modified (or if `--fetch` was not run earlier), recalculate SRI hashes:
```bash
python3 bazel/3rdparty/update_integrity.py <module> <new_version> [--fetch]
```

### Step 5: Update Root `MODULE.bazel` & Overrides

If not updated via `--update-root` in Step 2:
1. Open `MODULE.bazel` in repository root.
2. Update the version in `bazel_dep(name = "<module>", version = "<new_version>", dev_dependency = True)`.
3. If `<module>` has a `single_version_override`, update its `version` attribute as well.

### Step 6: Shutdown Bazel & Verify

1. Clear the Bazel server's in-memory registry cache:
   ```bash
   bazel shutdown
   ```

2. Run smoke tests:
   ```bash
   INVOCATION_ID=$(uuidgen) && echo "Invocation ID: ${INVOCATION_ID}" && bazel test //bazel/tests/... --config=linux_amd64 --invocation_id=${INVOCATION_ID}
   ```

3. If updating dnf5 core dependencies, verify all platform targets build:
   ```bash
   for p in linux_amd64 linux_arm64 osx_amd64 osx_arm64; do
     INVOCATION_ID=$(uuidgen) && echo "Invocation ID: ${INVOCATION_ID}" && bazel build //bazel/release:dnf5 --config=$p -c opt --invocation_id=${INVOCATION_ID}
   done
   ```

4. If a new module was introduced to `bazel/3rdparty`:
   Ensure its name is added to `matchPackageNames` under the `bazel-module` ignore rule in `.github/renovate.json`.
