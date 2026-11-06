# Pitfalls & Best Practices for `bazel/3rdparty`

This document summarizes known edge cases and best practices when working with third-party C/C++ and Rust libraries in `bazel/3rdparty`.

---

## 1. Local Registry Immutability & Caching

- **Committed versions are immutable**:
  Never edit a committed version directory in-place. Always bump to a new version:
  - If upstream version is unchanged: bump the internal suffix, e.g. `1.19.dnf5.1` -> `1.19.dnf5.2`.
  - If upgrading upstream version: create the new version directory, e.g. `2.16.0` or `2.16.0.dnf5.1`.
- **Bazel server caches registry files**:
  The Bazel server caches registry metadata and source hashes in memory. After modifying or creating any file in `bazel/3rdparty`, you **must** run:
  ```bash
  bazel shutdown
  ```
  before running `bazel build` or `bazel test`.

---

## 2. Renovate Bot & BCR Separation

- Modules in `bazel/3rdparty` are hosted locally in this repository and do not exist on BCR (or exist in incompatible configurations).
- Renovate bot's `bazel-module` manager reads all `bazel_dep` declarations in the root `MODULE.bazel`.
- Any module residing in `bazel/3rdparty` **must** be listed in `.github/renovate.json` under `packageRules`:
  ```json
  {
    "description": "Ignore private Bzlmod dependencies hosted in the local registry bazel/3rdparty",
    "matchManagers": ["bazel-module"],
    "matchPackageNames": [
      "json-c",
      "libacl",
      "libmodulemd",
      "libpkgmanifest",
      "librepo",
      "libsmartcols",
      "libsolv",
      "popt",
      "rpm",
      "rpm-sequoia",
      "toml11"
    ],
    "enabled": false
  }
  ```
- If a new module is added to `bazel/3rdparty`, add its name to `matchPackageNames` in `.github/renovate.json`.

---

## 3. C/C++ Include Hygiene

- **Root quote include path collision**:
  Bazel adds every repository root to the `-iquote` path of consumers. If a library has `config.h` at its root, it will shadow `#include "config.h"` in other packages.
  *Fix*: Keep generated headers in a subfolder and add them using `-iquote` or helper functions in your overlays (`repo_path()`, `private_includes()`).
- **Private include isolation**:
  Use `implementation_deps` instead of `deps` for internal headers so generic file names (`c.h`, `debug.h`, `system.h`) do not leak into downstream consumers.
- **Flat header staging**:
  Upstream libraries like `libsolv` and `librepo` include sibling headers by bare name (e.g. `#include "repo.h"`). Stage them into a single directory using `bazel_skylib`'s `copy_file` rule before exposing them in `hdrs`.

---

## 4. Portability & Toolchains

- **Target glibc 2.28 Baseline (AlmaLinux 8)**:
  Prebuilt binaries target glibc 2.28 as the oldest supported Linux distribution. Any configure-time header (`config.h`, `features.h`) must be generated inside an AlmaLinux 8 container. Never use newer glibc symbols like `arc4random()` or Linux 5.x+ specific syscalls without fallback guards.
- **macOS libc++ Strictness**:
  `libc++` is stricter than GNU `libstdc++`:
  - Missing transitive standard headers (always explicitly include `<iterator>`, `<stdexcept>`, `<sstream>`, etc.).
  - No `std::chrono::parse` support.
  - Strict POSIX regex compliance.
  Apply small upstreamable patches under `patches/` when necessary.
- **macOS Frameworks**:
  The hermetic macOS LLVM SDK only includes minimal frameworks by default. If a dependency needs additional Apple frameworks (like CoreServices or AppKit for glib/gio), declare them in the root `MODULE.bazel` under `osx.frameworks`.
- **OpenSSL aarch64 Linux Non-PIC Assembly**:
  OpenSSL assembly routines are not PIC on Linux ARM64. Keep `--@openssl//:use-no-asm-fallback` active for `linux_arm64` in `.bazelrc`.

---

## 5. Verification Checklist

Whenever modifying a 3rdparty module:
1. Run `python3 bazel/3rdparty/update_integrity.py <module> <version> [--fetch]`
2. `bazel shutdown`
3. Link/run smoke test:
   ```bash
   INVOCATION_ID=$(uuidgen) && echo "Invocation ID: ${INVOCATION_ID}" && bazel test //bazel/tests/... --config=linux_amd64 --invocation_id=${INVOCATION_ID}
   ```
4. Full cross-platform verification:
   ```bash
   for p in linux_amd64 linux_arm64 osx_amd64 osx_arm64; do
     INVOCATION_ID=$(uuidgen) && echo "Invocation ID: ${INVOCATION_ID}" && bazel build //bazel/release:dnf5 --config=$p -c opt --invocation_id=${INVOCATION_ID}
   done
   ```
