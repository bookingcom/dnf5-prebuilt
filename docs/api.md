# Public API Reference (`@dnf5-prebuilt//dnf5-prebuilt:defs.bzl`)

This document provides complete reference documentation for all public rules, macros, providers, and toolchains exposed by `dnf5-prebuilt`.

Load these symbols in your `BUILD` or `.bzl` files:

```starlark
load(
    "@dnf5-prebuilt//dnf5-prebuilt:defs.bzl",
    "Dnf5Info",
    "current_dnf5_toolchain",
    "dnf5_toolchain",
    "dnf_config",
    "rpm_layer",
    "rpm_lock",
    "rpm_mark",
    "rpm_merge",
    "rpmdb_inject",
    "tar_compress",
    "tar_dedup",
)
```

---

## Table of Contents

- [Container Layer Assembly](#container-layer-assembly)
  - [`rpm_layer`](#rpm_layer)
  - [`rpm_merge`](#rpm_merge)
  - [`tar_dedup`](#tar_dedup)
  - [`rpmdb_inject`](#rpmdb_inject)
  - [`tar_compress`](#tar_compress)
- [Dependency Resolution and Locking](#dependency-resolution-and-locking)
  - [`rpm_lock`](#rpm_lock)
  - [`dnf_config`](#dnf_config)
  - [`rpm_mark`](#rpm_mark)
- [Toolchains and Providers](#toolchains-and-providers)
  - [`dnf5_toolchain`](#dnf5_toolchain)
  - [`current_dnf5_toolchain`](#current_dnf5_toolchain)
  - [`Dnf5Info`](#dnf5info)
- [Bzlmod Extension](#bzlmod-extension)
  - [`dnf5`](#dnf5)

---

## Container Layer Assembly

### `rpm_layer`

```starlark
rpm_layer(name, rpms, rpmdb = None, compress = None, out = None, gpgcheck = False, gpgkeys = [], **kwargs)
```

Macro that assembles RPM packages into an OCI container layer tarball using a deterministic, multi-pass pipeline:
1. **Streaming Extraction and Merging**: Merges all RPMs into an uncompressed tar archive using `bsdtar` in memory without unpacking files to disk (with optional per-RPM GPG signature validation).
2. **Deduplication**: Deduplicates file and directory paths in the tar archive, keeping the last occurrence to match installation order.
3. **RPM Database Injection** (optional): Injects an updated SQLite `rpmdb` under `/var/lib/rpm/rpmdb.sqlite`.
4. **Compression** (optional): Compresses the layer archive using `gzip` or `zstd`.

#### Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `rpms` | `list of labels` | *mandatory* | List of RPM package files to merge into the layer (e.g. `@<lock_repo>//:rpms` exposed by `dnf5.lock`). |
| `rpmdb` | `label` | `None` | Optional updated SQLite `rpmdb` database file to inject into `/var/lib/rpm/rpmdb.sqlite` and use as keystore source if `gpgcheck = True`. |
| `compress` | `string` | `None` | Optional compression format: `"gzip"` (`.tar.gz`) or `"zstd"` (`.tar.zst`). Uncompressed tar when omitted. |
| `out` | `string` | `None` | Optional explicit output filename. Defaults to `<name>.tar` or `<name>.tar.{gz,zst}`. |
| `gpgcheck` | `bool` | `False` | Optional flag to enable GPG signature validation of all RPM packages prior to merging. |
| `gpgkeys` | `list of labels` | `[]` | Optional list of GPG public key files used to verify package signatures when `gpgcheck = True`. |
| `**kwargs` | `dict` | | Common rule attributes forwarded to the final rule (e.g. `visibility`, `tags`). |

#### Example

```starlark
load("@dnf5-prebuilt//dnf5-prebuilt:defs.bzl", "rpm_layer")

rpm_layer(
    name = "curl_layer",
    gpgcheck = True,
    rpmdb = ":base_with_curl_rpmdb",
    rpms = ["@curl_lock//:rpms"],
    compress = "gzip",
)
```

---

### `rpm_merge`

```starlark
rpm_merge(name, rpms, gpgcheck = False, gpgkeys = [], rpmdb = None, out = None)
```

Rule that merges RPM packages into an uncompressed tar archive using `bsdtar` directly from RPM payload archives in streaming mode. When `gpgcheck = True`, creates a GPG keystore action and individual verification actions per RPM, which the bsdtar action depends on.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `rpms` | `list of labels` | *mandatory* | RPM package files (`.rpm`) to extract and merge. |
| `gpgcheck` | `bool` | `False` | Optional flag to enable GPG signature validation of all RPM packages prior to merging. |
| `gpgkeys` | `list of labels` | `[]` | Optional list of GPG public key files used to verify package signatures. |
| `rpmdb` | `label` | `None` | Optional rpmdb SQLite database file containing trusted GPG keys. |
| `out` | `string` | `None` | Optional output tar file name. Defaults to `<name>.tar`. |

---

### `tar_dedup`

```starlark
tar_dedup(name, src, out = None)
```

Rule that deduplicates directory entries and files in an uncompressed tar archive, preserving the last occurrence of each file to match package installation ordering.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `src` | `label` | *mandatory* | Input uncompressed tar archive. |
| `out` | `string` | `None` | Optional output tar file name. Defaults to `<name>.tar`. |

---

### `rpmdb_inject`

```starlark
rpmdb_inject(name, src, rpmdb, out = None)
```

Rule that injects an SQLite `rpmdb` file into a tar archive under `/var/lib/rpm/rpmdb.sqlite`, creating intermediate directories with standard `0755 root:root` permissions.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `src` | `label` | *mandatory* | Input uncompressed tar archive. |
| `rpmdb` | `label` | *mandatory* | SQLite `rpmdb` file to inject. |
| `out` | `string` | `None` | Optional output tar file name. Defaults to `<name>.tar`. |

---

### `tar_compress`

```starlark
tar_compress(name, src, compress, out = None)
```

Rule that compresses an uncompressed tar archive using `bsdtar` with `gzip` or `zstd`, stripping non-deterministic timestamps (`--options=gzip:!timestamp`).

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `src` | `label` | *mandatory* | Input tar archive to compress. |
| `compress` | `string` | *mandatory* | Compression format: `"gzip"` or `"zstd"`. |
| `out` | `string` | `None` | Optional output file name. Defaults to `<name>`. |

---

## Dependency Resolution and Locking

### `rpm_lock`

```starlark
rpm_lock(
    name,
    packages,
    config = None,
    base_rpmdb = None,
    arch = ["x86_64", "noarch"],
    releasever = None,
    repo_configs = [],
    repo_files = [],
    exclude = [],
    forcearch = "",
    nobest = False,
    install_weak_deps = True,
    module_enable = [],
    module_platform_id = "",
    excludepkgs = [],
    vars = {},
    debug = False,
    out = None,
)
```

Rule and executable that resolves dependencies using `dnf5 lock` and generates a deterministic JSON lockfile. Supports multi-layer dependency solving on top of an existing container `base_rpmdb`.

Running `bazel run <target>` updates the lockfile in place in the source tree using `BUILD_WORKSPACE_DIRECTORY`.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `packages` | `list of strings` | *mandatory* | List of package specs to resolve (names, NEVRAs, provides). |
| `config` | `label` | `None` | Optional pre-rendered `dnf_config` target. When omitted, `releasever` and `repo_configs` must be provided. |
| `base_rpmdb` | `label` | `None` | Optional base `rpmdb.sqlite` with already installed packages for multi-layer resolution. |
| `arch` | `list of strings` | `["x86_64", "noarch"]` | Target CPU architectures to resolve for. |
| `releasever` | `string` | `None` | Distribution release version (e.g. `"9"`). |
| `forcearch` | `string` | `""` | Override architecture passed to `--forcearch`. |
| `nobest` | `bool` | `False` | Allow older package candidates (`--no-best`). |
| `install_weak_deps` | `bool` | `True` | Include weak/recommended dependencies. |
| `module_enable` | `list of strings` | `[]` | Module streams to enable before resolving (`NAME:STREAM`). |
| `module_platform_id` | `string` | `""` | Platform module (e.g. `'platform:el9'`) streams resolve against. |
| `excludepkgs` | `list of strings` | `[]` | Package NEVRA globs hidden from solver (`excludepkgs=`). |
| `exclude` | `list of strings` | `[]` | Package names or NEVRA globs to exclude and prune from the dependency tree. |
| `vars` | `dict of strings` | `{}` | Custom variables passed via `--setvar=NAME=VALUE`. |
| `repo_configs` | `list of labels` | `[]` | `.repo` configuration files. |
| `repo_files` | `list of labels` | `[]` | Repository metadata files (repodata XMLs, signatures). |
| `debug` | `bool` | `False` | Include debugging fields (`dependencies`, `transitive_dependencies`, `recommends`, `supplements`) in the lockfile. |
| `out` | `output` | `None` | Explicit output file. Defaults to `<name>.lock.json`. |

#### Lockfile Schema

See [Lockfile Specification (`docs/lockfile-spec.md`)](lockfile-spec.md) for the complete specification.

The generated JSON lockfile contains:
- `version`: Lockfile schema version (currently `1`).
- `arch`: Target architecture string.
- `requested`: Array of requested package names.
- `install_order`: Array of package names in topological installation order (Kahn's algorithm).
- `packages`: Array of resolved package objects in topological installation order, each with:
  - `name`: Package name.
  - `version`: Version-release (EVR).
  - `arch`: Architecture.
  - `url`: Download URL resolved from repodata.
  - `integrity`: Subresource Integrity string (`sha256-<base64>`).
  - `requested`: Present and `true` only when the package was directly requested.
  - When `debug = True` (`--debug`), each package object additionally includes `dependencies`, `transitive_dependencies`, `recommends` (if non-empty), and `supplements` (if non-empty).

```json
{
  "version": 1,
  "arch": "x86_64,noarch",
  "requested": ["curl"],
  "install_order": ["libcurl", "curl"],
  "packages": [
    {
      "name": "libcurl",
      "version": "8.7.1-1.el9",
      "arch": "x86_64",
      "url": "https://mirror.example.com/Packages/l/libcurl-8.7.1-1.el9.x86_64.rpm",
      "integrity": "sha256-abc..."
    },
    {
      "name": "curl",
      "version": "8.7.1-1.el9",
      "arch": "x86_64",
      "url": "https://mirror.example.com/Packages/c/curl-8.7.1-1.el9.x86_64.rpm",
      "integrity": "sha256-xyz...",
      "requested": true
    }
  ]
}
```

---

### `dnf_config`

```starlark
dnf_config(
    name,
    arch,
    releasever,
    repo_configs,
    repo_files = [],
    forcearch = "",
    nobest = False,
    install_weak_deps = True,
    module_enable = [],
    module_platform_id = "",
    excludepkgs = [],
    vars = {},
)
```

Rule that renders a hermetic `dnf.conf` and repository drop-ins under `repos.d/`, generating a `DnfConfigInfo` provider and preamble argument file pinning dnf5 to the hermetic sandbox.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `arch` | `list of strings` | *mandatory* | Target CPU architectures (e.g. `["x86_64", "noarch"]`). |
| `releasever` | `string` | *mandatory* | Distribution release version passed to `--releasever` (e.g. `"9"`). |
| `repo_configs` | `list of labels` | *mandatory* | Template `.repo` or `.conf` files. `@REPO_DIR@` is expanded to the repository directory. |
| `repo_files` | `list of labels` | `[]` | Repository files (repodata XMLs, signatures). |
| `forcearch` | `string` | `""` | Forced solver architecture. Defaults to first non-noarch entry in `arch`. |
| `nobest` | `bool` | `False` | Allow older candidates when newest requested package cannot be installed. |
| `install_weak_deps` | `bool` | `True` | Install weak/recommended dependencies. |
| `module_enable` | `list of strings` | `[]` | Module streams (`NAME:STREAM`) to enable before resolving. |
| `module_platform_id` | `string` | `""` | Platform module stream ID (e.g. `'platform:el9'`). |
| `excludepkgs` | `list of strings` | `[]` | Package NEVRA globs hidden from solver (`excludepkgs=`). |
| `vars` | `dict of strings` | `{}` | Custom variables passed to dnf5 via `--setvar=NAME=VALUE`. |

---

### `rpm_mark`

```starlark
rpm_mark(name, rpms, base_rpmdb = None, out = None)
```

Rule that records RPM packages into an SQLite `rpmdb` database without installing files or executing scripts, producing a reproducible `rpmdb.sqlite` with normalized timestamps (`SOURCE_DATE_EPOCH=0`).

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `rpms` | `list of labels` | *mandatory* | RPM package files (`.rpm`) to record in the database. |
| `base_rpmdb` | `label` | `None` | Optional base `rpmdb.sqlite` file to record packages on top of. |
| `out` | `output` | `None` | Optional output file name. Defaults to `<name>/rpmdb.sqlite`. |

---

## Toolchains and Providers

### `dnf5_toolchain`

```starlark
dnf5_toolchain(name, dnf5, rpm, files = [], version = "")
```

Rule defining a dnf5 toolchain resolved for an execution platform.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Toolchain rule name. |
| `dnf5` | `label` | *mandatory* | Path to the `bin/dnf5` launcher of the distribution. |
| `files` | `list of labels` | `[]` | Complete distribution files (runtime binaries, shared libraries, plugins). |
| `rpm` | `label` | *mandatory* | Path to the `bin/rpm` launcher of the distribution. |
| `version` | `string` | `""` | Toolchain distribution version string. |

---

### `current_dnf5_toolchain`

```starlark
current_dnf5_toolchain(name, binary = "dnf5")
```

Rule exposing the resolved launcher (`dnf5` or `rpm`) for the execution platform as an executable target with runfiles and template variables (`$(DNF5)` or `$(RPM)`).

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `binary` | `string` | `"dnf5"` | Which launcher binary to expose: `"dnf5"` or `"rpm"`. |

---

### `Dnf5Info`

Provider returned by `dnf5_toolchain` and `current_dnf5_toolchain`:

- `dnf5`: `File` pointing to `bin/dnf5`.
- `rpm`: `File` pointing to `bin/rpm`.
- `files`: `depset of File` with the entire distribution.
- `version`: Distribution version string.

---

## Bzlmod Extension

### `dnf5`

Module extension defined in `@dnf5-prebuilt//dnf5-prebuilt:extensions.bzl`.

#### `dnf5.toolchains`

```starlark
dnf5 = use_extension("@dnf5-prebuilt//dnf5-prebuilt:extensions.bzl", "dnf5")
dnf5.toolchains(name = "dnf5", version = "5.4.6.0")
use_repo(dnf5, "dnf5_toolchains")

register_toolchains("@dnf5_toolchains//:all")
```

Fetches hermetic prebuilt distributions for Linux (`amd64`, `arm64`) and macOS (`amd64`, `arm64`).

For testing local or unreleased builds, setting `--repo_env=DNF5_PREBUILT_DIST_DIR=/path` overrides download URLs to read tarballs from that directory without integrity checks.

#### `dnf5.lock`

```starlark
dnf5.lock(
    name = "curl_lock",
    lockfile = "//:curl_lock.lock.json",
)
use_repo(dnf5, "curl_lock")
```

Reads a JSON lockfile produced by `rpm_lock`, creates an `http_file` repository for each locked RPM (verified by its `integrity` digest), and generates a hub repository `@<name>` exposing the RPMs in topological `install_order`:

- `@<name>//:rpms`: `filegroup` containing all locked RPM files ordered by `install_order`, suitable for passing directly to `rpm_layer(rpms = ["@<name>//:rpms"])` and `rpm_mark(rpms = ["@<name>//:rpms"])`.
- `@<name>//:<pkg>`: `alias` for each individual package in the lockfile.
- `@<name>//:defs.bzl`: Starlark module exporting `RPMS` (ordered list of label strings) and `PACKAGES` (ordered list of package names).
