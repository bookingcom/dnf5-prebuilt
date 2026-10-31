# dnf5-prebuilt

Prebuilt [dnf5](https://github.com/rpm-software-management/dnf5) — the Fedora
package manager — for **Linux (x86_64, arm64)** and **macOS (Intel, Apple
silicon)**, built hermetically from source with Bazel, and a Bazel module to use
it as a toolchain (for example to resolve, download and install RPMs into a root
filesystem from a build).

- dnf5 **5.4.6.0** with libdnf5, libdnf5-cli and the dnf5/libdnf5 plugins
  (builddep, changelog, config-manager, copr, manifest, repoclosure,
  repomanage, reposync, actions, expired-pgp-keys, local), plus two command
  plugins of this repository: `lock` (resolves packages into a JSON lockfile)
  and `rpmdb-mark` (records packages in an rpmdb without installing them).
- Every dependency (rpm 6.1 with Sequoia OpenPGP, libsolv, librepo, curl,
  OpenSSL, glib, libmodulemd, …) is built from source with a hermetic LLVM
  toolchain; nothing is taken from the build host.
- Linux binaries need glibc ≥ 2.28 (RHEL/CentOS/Alma/Rocky 8, Debian 10,
  Ubuntu 20.04 and newer); macOS binaries need macOS 14 or newer.
- The Bazel build is verified against upstream's CMake build with an
  action-graph diff (see [Build parity](#build-parity)).

## Using the Bazel module

```starlark
# MODULE.bazel
bazel_dep(name = "dnf5-prebuilt", version = "5.4.6.0")

dnf5 = use_extension("@dnf5-prebuilt//dnf5-prebuilt:extensions.bzl", "dnf5")
dnf5.toolchains()
use_repo(dnf5, "dnf5_toolchains")

register_toolchains("@dnf5_toolchains//:all")
```

The toolchain type is `@dnf5-prebuilt//dnf5-prebuilt:toolchain_type` and
provides `Dnf5Info` (`dnf5`: the launcher, `files`: the whole distribution,
`version`). `@dnf5-prebuilt//dnf5-prebuilt:current_toolchain` exposes the
toolchain resolved for the execution platform:

```starlark
# In a rule implementation
load("@dnf5-prebuilt//dnf5-prebuilt:defs.bzl", "Dnf5Info")

def _impl(ctx):
    dnf5 = ctx.toolchains["@dnf5-prebuilt//dnf5-prebuilt:toolchain_type"].dnf5_info
    ctx.actions.run(
        executable = dnf5.dnf5,
        tools = dnf5.files,
        arguments = ["--version"],
        ...
    )

my_rule = rule(
    implementation = _impl,
    toolchains = ["@dnf5-prebuilt//dnf5-prebuilt:toolchain_type"],
    ...
)
```

```starlark
# In a BUILD file: $(DNF5) points at the launcher
genrule(
    name = "dnf5_version",
    outs = ["dnf5_version.txt"],
    cmd = "$(DNF5) --version > $@",
    toolchains = ["@dnf5-prebuilt//dnf5-prebuilt:current_toolchain"],
    tools = ["@dnf5-prebuilt//dnf5-prebuilt:current_toolchain"],
)
```

You can also run dnf5 directly on the host platform:

```sh
bazel run @dnf5-prebuilt//dnf5-prebuilt:dnf5 -- --version
```

`dnf5.toolchains(name = "...", version = "...")` selects another name for the
generated repositories (`<name>_toolchains`, `<name>_<platform>`) or another
published dnf5 version.

### Rules: `rpm_lock`, `rpm_mark`, `dnf_config`

`@dnf5-prebuilt//dnf5-prebuilt:defs.bzl` also has rules that run the
registered toolchain's dnf5 hermetically: every dnf5 directory (cache, logs,
state, variables, plugin configuration) points into the action's scratch
directory or the generated configuration, never at the host's `/etc`, `/var`
or `$HOME`.

```starlark
load("@dnf5-prebuilt//dnf5-prebuilt:defs.bzl", "rpm_lock", "rpm_mark")

# Resolves the packages with `dnf5 lock` into base_lock.lock.json.
rpm_lock(
    name = "base_lock",
    arch = ["x86_64", "noarch"],
    packages = ["bash"],
    releasever = "9",
    repo_config = "ol9.repo",
)

# Records the packages with `dnf5 rpmdb-mark` in var/lib/rpm/rpmdb.sqlite,
# without installing them.
rpm_mark(
    name = "base_rpmdb",
    arch = "x86_64",
    packages = ["curl"],
    releasever = "9",
    repo_config = "ol9.repo",
)
```

- `rpm_lock` writes a JSON lockfile with, per package, `name`, `version`,
  `arch`, `nevra`, `url`, the SRI `integrity`, `checksum` and `dependencies`
  (plus `recommends`/`supplements` when the package has any) and provides
  `RpmLockFileInfo`. `lock_files` solves a layer on top of earlier lockfiles,
  `exclude` prunes packages from the result (`dnf5 lock --prune`), and
  `excludepkgs`, `forcearch`, `install_weak_deps`, `module_enable`,
  `module_platform_id` and `nobest` map to the dnf options of the same name.
  `bazel run` of an `rpm_lock` target writes the lockfile into the source tree.
- `dnf_config` renders the configuration on its own (`DnfConfigInfo`) for
  custom rules; `DNF5_PREAMBLE` is the list of dnf5 options they run under.
- `dnf5 lock` and `dnf5 rpmdb-mark` are command plugins of this repository
  (`bazel/dnf5/plugins/`) and also work outside Bazel; see `dnf5 lock --help`.

Their tests are in [`e2e/smoke_test`](e2e/smoke_test). The lockfiles of the
`rpm_lock` cases there are checked in under `testdata/lock_golden/`; accept a
change with `bazel run //testdata:lock_golden` in that directory.

## Using the archives directly

Every [release](https://github.com/bookingcom/dnf5-prebuilt/releases) has one
archive per platform, `dnf5-<version>-<platform>.tar.gz`. Extract it anywhere
and run `dnf5/bin/dnf5`:

```sh
tar xzf dnf5-5.4.6.0-linux_amd64.tar.gz
./dnf5/bin/dnf5 --version

# Bootstrap a Fedora 44 root filesystem (as root, or in a user namespace with
# subordinate ids, so that rpm can chroot and chown).
./dnf5/bin/dnf5 -y --installroot="$PWD/rootfs" --releasever=44 --forcearch=x86_64 \
    --setopt=reposdir=/dev/null \
    --repofrompath=fedora,https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/os/ \
    --setopt=fedora.gpgcheck=1 \
    --setopt=fedora.gpgkey=https://src.fedoraproject.org/rpms/fedora-repos/raw/f44/f/RPM-GPG-KEY-fedora-44-primary \
    --repo=fedora install bash coreutils-single
```

The archive is relocatable. `bin/dnf5` is a small launcher that points dnf5,
libdnf5 and rpm at the bundled plugins and configuration before running
`libexec/dnf5`:

| Setting | Default | Override |
|---|---|---|
| rpm configuration (`rpmrc`, macros) | `<prefix>/lib/rpm` | `RPM_CONFIGDIR` |
| dnf5 command plugins | `<prefix>/lib/dnf5/plugins` | `DNF5_PLUGINS_DIR` |
| libdnf5 plugins and their configuration | `<prefix>/lib/libdnf5/plugins`, `<prefix>/etc/dnf/libdnf5-plugins` | `--setopt=pluginpath=…`, `--setopt=pluginconfpath=…` |
| CA bundle for HTTPS repositories | first of `/etc/pki/tls/certs/ca-bundle.crt`, `/etc/ssl/certs/ca-certificates.crt`, `/etc/ssl/ca-bundle.pem`, `/etc/ssl/cert.pem` | `SSL_CERT_FILE` or `--setopt=sslcacert=…` |

Set `DNF5_PREBUILT_NO_DEFAULTS=1` to skip the `--setopt` defaults. Everything
else behaves like upstream dnf5 configured with `--prefix=/usr` (e.g. without
`--installroot` it reads `/etc/dnf/dnf.conf` and `/etc/yum.repos.d`).

Notes:

- **macOS** can resolve and download packages, query repositories and build
  installroots with `--setopt=tsflags=noscripts`; scriptlets are Linux
  programs and cannot run there.
- rpm-sequoia uses Sequoia's pure-Rust cryptography backend.
- Not included: the D-Bus daemon (`dnf5daemon-*`), the systemd-dependent
  `automatic` and `needs-restarting` plugins, appstream/rhsm/python plugin
  loaders, language bindings, translations and documentation.

## Building from source

Requirements: [Bazelisk](https://github.com/bazelbuild/bazelisk) (the Bazel
version is pinned in `.bazelversion`) and network access to fetch sources. No
compiler or system libraries are needed: the hermetic LLVM toolchain builds
everything, including libc++, and cross-compiles to every platform from any
host.

```sh
# Relocatable distribution archive for a platform
bazel build //bazel/release:dnf5 --config=linux_amd64 -c opt   # or linux_arm64, osx_amd64, osx_arm64

# Just dnf5 (runs from bazel-bin)
bazel build @dnf5//:dnf5 --config=linux_amd64

# Smoke tests of the third-party libraries
bazel test //bazel/tests/... --config=linux_amd64

# Test the public module against locally built archives
mkdir -p /tmp/dist && cp -L bazel-bin/bazel/release/dnf5.tar.gz /tmp/dist/dnf5-5.4.6.0-linux_amd64.tar.gz
(cd e2e/smoke_test && bazel test //... --repo_env=DNF5_PREBUILT_DIST_DIR=/tmp/dist)
```

`--config=rbe` enables remote execution (configure the endpoint and
credentials in `.bazelrc.user`, which is git-ignored). Remote actions run in
the Ubuntu 24.04 image of toolchains_buildbuddy; use another image with

```
common --repo_env=RBE_CONTAINER_IMAGE=docker://<registry>/<image>@sha256:<digest>
```

## Repository layout

| Path | What |
|---|---|
| `dnf5-prebuilt/` | **Public API**: module extension, toolchain rules, release versions. Depends only on `@platforms`. |
| `bazel/extensions.bzl` | `dnf5_extension`: fetches the upstream dnf5 release (`@dnf5`) with `http_archive`. |
| `bazel/dnf5/` | Bazel overlay for dnf5 (`dnf5.BUILD.bazel`), upstreamable patches, macOS compatibility shims, and the `lock`/`rpmdb-mark` command plugins of this repository (`plugins/`). |
| `bazel/3rdparty/` | Local Bazel registry with the dependencies that are not in the BCR (or needed fixes). |
| `bazel/release/` | Distribution archive (`dist.bzl`, launcher, bundled licenses). |
| `bazel/tests/` | Toolchain and third-party library smoke tests. |
| `bazel/BUILD.bazel` | Target platforms and the remote execution platform. |
| `e2e/smoke_test/` | Consumer of the public module. |
| `tools/any2bazel/` | Build parity check against upstream's CMake build. |
| `tools/licenses/` | Collects the licenses of bundled components. |

Everything except `dnf5-prebuilt/` is private: it is only used to build the
archives, and its dependencies are `dev_dependency` modules that users of the
module never fetch.

## Build parity

`tools/any2bazel` compares Bazel's action graph for `@dnf5` with the CMake File
API model of upstream's build (configured in a Fedora 44 container): every
translation unit must be compiled with the same defines, flags and include
roots, and executables must link with equivalent flags. The current status is
**converged (0 errors)**; accepted differences are listed with their rationale
in [`any2bazel.json`](any2bazel.json). See
[`tools/any2bazel/README.md`](tools/any2bazel/README.md).

## Updating

- **dnf5**: bump `DNF5_VERSION`/`DNF5_SHA256` in `bazel/extensions.bzl`,
  rebase the patches in `bazel/dnf5/patches/`, update `dnf5.BUILD.bazel`, the
  reference configuration in `tools/any2bazel/` and
  `dnf5-prebuilt/private/versions.bzl`, then re-run the parity check.
- **Dependencies in `bazel/3rdparty`**: registry versions are immutable. Add a
  new version directory (e.g. `1.2.3.dnf5.1` for a changed overlay), refresh
  its integrity with `bazel/3rdparty/update_integrity.py <module> <version>`
  and bump the `bazel_dep`.
- **Licenses**: run `tools/licenses/collect.py` after dependency changes.

## Releasing

Push a tag `v<dnf5 version>` (or `v<dnf5 version>.<n>` for rebuilds). The
release workflow builds the four archives, stamps their integrity into the
module's `versions.bzl` in the release source archive, publishes the GitHub
release and opens a pull request against the Bazel Central Registry.

Repository variables and secrets used by the workflows:

| Name | Kind | Purpose |
|---|---|---|
| `BUILDBUDDY_ENDPOINT` | variable | Optional BuildBuddy host name (gRPC at `grpcs://<host>`, invocation links at `https://<host>/invocation/`). |
| `BUILDBUDDY_API_KEY` | secret | API key for that BuildBuddy. Without both, CI uses the GitHub Actions disk cache. |
| `BCR_PUBLISH_TOKEN` | secret | Token used to open the Bazel Central Registry pull request. |

## License

The build definitions, scripts and patches in this repository are licensed
under the [Apache License 2.0](LICENSE). The prebuilt archives contain
third-party software under their own licenses, mostly GPL-2.0-or-later and
LGPL-2.1-or-later (dnf5, rpm, librepo, …) plus permissive licenses; see
`share/licenses/THIRD_PARTY_NOTICES.md` in every archive and
[`bazel/release/licenses`](bazel/release/licenses).
