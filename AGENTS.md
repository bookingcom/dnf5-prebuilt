# AGENTS.md

Notes for LLM agents working on this repository (CLAUDE.md, CODEX.md and
GEMINI.md are symlinks to this file). Read README.md first for what the project
is; this file records the rules and the non-obvious lessons.

## Ground rules

- **Public vs private.** `dnf5-prebuilt/` is the public API (what BCR users
  get). It must not reference any other package of this repository nor any
  `dev_dependency` module; today it only uses `@platforms`. Everything else is
  private build infrastructure and every module it uses is a `dev_dependency`.
- **One commit per step** (e.g. one third-party library = registry entry +
  `MODULE.bazel` + `MODULE.bazel.lock` + its smoke test). Message ends with the
  attribution line required by the session.
- **Never publish org-internal references**; this repository is public
  (Apache-2.0). Do not use company-internal services from here.
- **Do not delete or overwrite `.bazelrc.user`**: it is git-ignored and holds
  the user's remote execution credentials. Never print it either.
- The user's global gitignore ignores `*.patch`; `.gitignore` re-includes it.
  Run `git status --ignored` before committing new kinds of files.
- **Git worktrees must be created under `.worktrees`** (e.g.
  `git worktree add .worktrees/<branch>`). Both `.bazelignore` and `REPO.bazel`
  ignore `.worktrees` and `e2e/*` so Bazel does not scan or recurse into nested
  worktrees or end-to-end test workspaces.
- Avoid `genrule`; use bazel_skylib/bazel_lib/tar.bzl rules or small Starlark
  rules (see `bazel/release/dist.bzl`). Languages: C/C++ (hermetic LLVM), Rust
  via `rules_rs`, Python via `aspect_rules_py` if ever needed; ask the user
  before introducing anything else.
- Resolve versions from the registry (`https://bcr.bazel.build/modules/<m>/metadata.json`)
  or upstream tags; never from memory.

## Layout

- `bazel/extensions.bzl` — `dnf5_extension` (`http_archive` of the upstream
  release + `bazel/dnf5/dnf5.BUILD.bazel` + `bazel/dnf5/patches/*`).
- `bazel/dnf5/dnf5.BUILD.bazel` — mirrors upstream CMake: `common_*` (one copy
  per consumer, like CMake's object library), `libdnf5_obj` → `libdnf5`
  (`cc_shared_library`), `libdnf5_cli_obj` → `libdnf5-cli`, `dnf5`
  (`cc_binary` with the sources, so any2bazel aligns it), plugins
  (`cc_shared_library` each). All third-party libraries are linked into one
  `libdnf5-deps` shared object (`cc_shared_library` refuses to link a static
  library into several shared objects; upstream links them as separate system
  `.so`s).
- `bazel/3rdparty/` — local registry (listed first in `.bazelrc`, BCR second).
- `bazel/release/` — distribution archive; `bin/dnf5` launcher sets
  `RPM_CONFIGDIR`, `DNF5_PLUGINS_DIR`, `pluginpath`, `pluginconfpath`,
  `sslcacert`.
- `tools/any2bazel/`, `any2bazel.json` — parity with upstream CMake.
- `docs/` — guides on [RPM dependency resolution and repodata integrity](docs/rpm-dependency-resolution.md) and [direct RPM-to-OCI layer merging with bsdtar](docs/rpm-to-oci-layer.md).

## Local registry (`bazel/3rdparty`)

- Committed versions are **immutable**. To change one, move it to a new
  version directory (`<upstream>.dnf5.<n>`, e.g. `libmodulemd/2.15.3.dnf5.1`),
  update `metadata.json` and the `bazel_dep`s. If other registry modules still
  request the old version, either keep it (Bazel reads the MODULE.bazel of
  every requested version; MVS then picks the root's newer one) or bump those
  modules too. Before the first push, prefer folding fixes into the commit that
  added the module.
- After editing files, run `bazel/3rdparty/update_integrity.py <module> <version> [--fetch]`.
- The Bazel server caches registry files: after editing a not-yet-committed
  entry in place, run `bazel shutdown`.
- Configure-time headers (`config.h` etc.) are captured by running the
  upstream configure in an AlmaLinux 8 container (**glibc 2.28 = the oldest
  supported target**, so no newer-glibc symbols such as `arc4random` sneak in),
  trimmed to what the sources use, with `#if defined(__APPLE__)` overrides.
  Plain-HTTP package mirrors may be blocked: point dnf at HTTPS `baseurl`s.
- Every library gets a link/run smoke test in `bazel/tests/3rdparty`
  (`linkstatic = True`).

## C/C++ pitfalls seen here

- **Bazel adds every dependency repository's root to the quote include path.**
  A dependency with a `config.h` at its root (BCR libxml2, json-c) shadows
  `#include "config.h"`. Keep generated headers in a subdirectory and pass it
  with `-iquote` (`repo_path()`/`private_includes()` helpers in the overlays;
  `Label(...).workspace_root` must live in a `.bzl`, `repository_name()` works
  in BUILD files). For dnf5 itself a root-relative path collided with a public
  header (patch 0001).
- Use `implementation_deps` for private include directories so generic names
  (`c.h`, `debug.h`, `system.h`) never leak into consumers.
- Libraries whose public headers include siblings by bare name need all
  public headers in one directory: stage them with skylib `copy_file`
  (libsolv, librepo).
- **libc++ is stricter than libstdc++** (missing `<iterator>`, `<stdexcept>`,
  `<exception>`, `<sstream>`, …; no `std::chrono::parse`;
  `high_resolution_clock` is `steady_clock`; strict POSIX regexes). Fix with
  small upstreamable patches.
- `cc_shared_library.user_link_flags` are not make-variable expanded (use
  `$ORIGIN`), `cc_binary.linkopts` are (use `$$ORIGIN`).
- Building a `cc_library` directly also links its per-library `.dylib` on
  macOS, which fails with undefined symbols; build top-level targets instead.
- The hermetic macOS SDK only contains the frameworks listed in
  `MODULE.bazel` (`osx.frameworks`); glib/gio needs the long list there.
- `openssl` assembly is not PIC on aarch64 Linux: `--@openssl//:use-no-asm-fallback`
  for `linux_arm64` (in `.bazelrc`).
- rpm 6 only supports OpenPGP through rpm-sequoia (Rust); it also provides the
  `rpmDigest*` API, so don't build `digest_openssl.cc`.

## dnf5 patches

Keep `bazel/dnf5/patches/` as `git format-patch` output on top of the release
tarball (author `dnf5-prebuilt`), listed in `DNF5_PATCHES` in
`bazel/extensions.bzl`. Workflow: extract the tarball into a scratch git repo,
commit it, apply the patches, commit fixes, `git format-patch <base>`.

## Verifying changes

```sh
bazel build //bazel/tests:hello --config=<platform>              # toolchain
bazel test //bazel/tests/... --config=linux_amd64                 # 3rd-party smoke tests
for p in linux_amd64 linux_arm64 osx_amd64 osx_arm64; do
  bazel build //bazel/release:dnf5 --config=$p -c opt; done       # all archives
tools/any2bazel/bazel_model.sh <workdir with model.cmake.json>    # must print CONVERGED
(cd e2e/smoke_test && bazel test //... --repo_env=DNF5_PREBUILT_DIST_DIR=<dir>)
```

A real end-to-end check is bootstrapping a Fedora root with the extracted
archive (README) as root, e.g. in a container (`unshare -r` alone cannot chown
to other ids).

## Environment notes (maintainer machine)

- RBE (`--config=rbe`, endpoint in `.bazelrc.user`) needs
  `--tls_certificate=/etc/pki/tls/certs/ca-bundle.crt` and
  `--noexperimental_remote_cache_chunking`, and its workers cannot pull the
  gcr.io image; local builds are the default. The image is overridable with
  `--repo_env=RBE_CONTAINER_IMAGE=docker://...@sha256:...` (`bazel/rbe.bzl`,
  which generates the parent of `//bazel:ubuntu24_04_amd64`).
- `bazel/downloader.cfg` adds cdn.kernel.org for kernel.org mirrors that may
  be unreachable.
