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
    "rpm_extract",
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
  - [`rpm_extract`](#rpm_extract)
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
rpm_layer(
    name,
    rpms,
    rpmdb = None,
    compress = None,
    out = None,
    gpgcheck = False,
    gpgkeys = [],
    exclude_docs = True,
    exclude_man = True,
    exclude_licenses = True,
    exclude_build_id = True,
    exclude_patterns = [],
    install_langs = None,
    **kwargs,
)
```

Macro that assembles RPM packages into an OCI container layer tarball using a deterministic, multi-pass pipeline:
1. **Streaming Extraction and Merging**: Merges all RPMs into an uncompressed tar archive using `bsdtar` in memory without unpacking files to disk (with optional per-RPM GPG signature validation). By default, minimal container layers are produced by excluding documentation (`*/share/doc/*`, `*/share/info/*`), man pages (`*/share/man/*`), license files (`*/share/licenses/*`), and `.build-id` debug links.
2. **Deduplication and Locale Filtering**: Deduplicates file and directory paths in the tar archive, keeping the last occurrence to match installation order. When `install_langs` is specified (e.g. `'en_US.UTF-8'`), filters out non-matching translation files in `/usr/share/locale` and `/usr/lib/locale` (mimicking DNF `--setopt=install_langs=...` and RPM `%_install_langs`), saving substantial disk space in minimal container layers.
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
| `exclude_docs` | `bool` | `True` | Exclude documentation and info files (`*/share/doc/*`, `*/share/info/*`). |
| `exclude_man` | `bool` | `True` | Exclude manual pages (`*/share/man/*`). |
| `exclude_licenses` | `bool` | `True` | Exclude license files (`*/share/licenses/*`). Set to `False` to preserve compliance notices in the layer. |
| `exclude_build_id` | `bool` | `True` | Exclude `.build-id` debug symbol links (`*/.build-id/*`). |
| `exclude_patterns` | `list of strings` | `[]` | Additional glob patterns to exclude during `bsdtar` extraction. |
| `install_langs` | `string or list of strings` | `None` | Language locales to keep (e.g. `'en_US.UTF-8'` or `['en_US.UTF-8']`), mimicking DNF `--setopt=install_langs=...` and RPM `%_install_langs`. Filters non-matching locale files in `/usr/share/locale` and `/usr/lib/locale`. |
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
rpm_merge(name, rpms, gpgcheck = False, gpgkeys = [], rpmdb = None, exclude_patterns = [], out = None)
```

Rule that merges RPM packages into an uncompressed cpio `newc` archive using `bsdtar` directly from RPM payload archives, assigning globally unique inode numbers per package so hard-link groups never collide across packages. When `gpgcheck = True`, creates a GPG keystore action and individual verification actions per RPM, which the merge action depends on.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `rpms` | `list of labels` | *mandatory* | RPM package files (`.rpm`) to extract and merge. |
| `gpgcheck` | `bool` | `False` | Optional flag to enable GPG signature validation of all RPM packages prior to merging. |
| `gpgkeys` | `list of labels` | `[]` | Optional list of GPG public key files used to verify package signatures. |
| `rpmdb` | `label` | `None` | Optional rpmdb SQLite database file containing trusted GPG keys. |
| `exclude_patterns` | `list of strings` | `[]` | Glob patterns to exclude when extracting RPMs with `bsdtar`. |
| `out` | `string` | `None` | Optional output file name. Defaults to `<name>.cpio`. |

---

### `rpm_extract`

```starlark
rpm_extract(name, rpms, files = [], dirs = [], gpgcheck = False, gpgkeys = [], rpmdb = None, **kwargs)
```

Macro that extracts specific files and directories from RPM packages and makes them available as individual targets in Bazel in a single action. Target names are prefixed with `name + "/" + path` (e.g. `:my_extract/usr/bin/curl`), preserving the fully-qualified relative path rather than shortening to basenames, preventing collisions when multiple `rpm_extract` macros in the same package extract similar paths.

#### Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Aggregate target name. Exposes all extracted files and directories. |
| `rpms` | `list of labels` | *mandatory* | List of RPM package files (`.rpm`) to extract from. |
| `files` | `list of strings` | `[]` | List of file paths to extract from the RPMs (e.g. `["usr/bin/curl", "usr/lib64/libcurl.so.4"]`). |
| `dirs` | `list of strings` | `[]` | List of directory paths to extract from the RPMs (e.g. `["etc/pki/tls", "usr/share/curl"]`). |
| `gpgcheck` | `bool` | `False` | Optional flag to enable GPG signature validation of all RPM packages prior to extraction. Automatically enabled if `gpgkeys` is provided. |
| `gpgkeys` | `list of labels` | `[]` | Optional list of GPG public key files used to verify package signatures. |
| `rpmdb` | `label` | `None` | Optional rpmdb SQLite database file containing trusted GPG keys. |
| `**kwargs` | `dict` | | Common rule attributes forwarded to generated targets (e.g. `visibility`, `tags`). |

#### Target Names and Visibility

Every path specified in `files` and `dirs` produces a target prefixed by `<name>/`:
- File paths (e.g. `"usr/bin/curl"` or `"/usr/bin/curl"`) produce file targets named `:<name>/usr/bin/curl` (`//package:<name>/usr/bin/curl`).
- Directory paths (e.g. `"etc/pki/tls"` or `"/etc/pki/tls/"`) produce directory TreeArtifact targets named `:<name>/etc/pki/tls` (`//package:<name>/etc/pki/tls`).
- The aggregate target `:<name>` (`//package:<name>`) builds and provides all extracted files and directories in a single action.

#### Symlink Dereferencing

If any extracted file or directory is or contains a symbolic link in the RPM package (including relative links, links climbing past root `../..` which are clamped at the tree root, and absolute links like `/usr/lib64/libcurl.so.4.7.0`), `rpm_extract` automatically resolves and follows the symlink chain across all provided RPMs. Every entry is fully dereferenced upon extraction, ensuring that all output targets are real files and directories rather than dangling or host-dependent symlinks. If a symlink target cannot be found in any of the provided RPM packages, extraction fails with an error.

#### Example

```starlark
load("@dnf5-prebuilt//dnf5-prebuilt:defs.bzl", "rpm_extract")

rpm_extract(
    name = "curl_extracted",
    rpms = [
        "@ol9_curl_rpm//file",
        "@ol9_libcurl_rpm//file",
    ],
    gpgcheck = True,
    rpmdb = ":ol9_curl_rpmdb",
    files = [
        "usr/bin/curl",
        "/usr/lib64/libcurl.so.4",
    ],
    dirs = [
        "usr/share/licenses/libcurl",
    ],
)

# Reference individual targets by their name-prefixed fully-qualified path:
sh_binary(
    name = "my_tool",
    srcs = ["run.sh"],
    data = [
        ":curl_extracted/usr/bin/curl",
        ":curl_extracted/usr/lib64/libcurl.so.4",
        ":curl_extracted/usr/share/licenses/libcurl",
    ],
)
```

---

### `tar_dedup`

```starlark
tar_dedup(name, src, install_langs = "", out = None)
```

Rule that deduplicates directory entries and files in an uncompressed tar or cpio `newc` archive, preserving the last occurrence of each file to match package installation ordering, resolving symlinked parent directories (e.g. usr-merge symlinks like `lib64 -> usr/lib64`) to prevent dangling paths underneath directory symlinks, and converting `newc` hard-link groups (where data is stored on the last member) into tar hard-link groups (where data is stored on the first surviving member). When `install_langs` is specified, filters out non-matching locale translation files.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `src` | `label` | *mandatory* | Input uncompressed tar or cpio `newc` archive. |
| `install_langs` | `string` | `""` | Optional language locales to keep (e.g. `'en_US.UTF-8'`), filtering out non-matching locale files. |
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
| `repo_configs` | `list of labels` | `[]` | List of `.repo` configuration files. |
| `repo_dirs` | `list of labels` | `[]` | List of directory artifacts containing `.repo` files. |
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
    repo_configs = [],
    repo_dirs = [],
    repo_files = [],
    forcearch = "",
    nobest = False,
    install_weak_deps = True,
    install_langs = "",
    module_enable = [],
    module_platform_id = "",
    excludepkgs = [],
    vars = {},
)
```

Rule that renders a hermetic `dnf.conf` and repository drop-ins under `repos.d/`, generating a `DnfConfigInfo` provider and preamble argument file pinning dnf5 to the hermetic sandbox. Repository configurations can be supplied as individual `.repo` files via `repo_configs`, as directory artifacts via `repo_dirs`, or both; they are merged together during rule execution into `repos.d/`. At least one of `repo_configs` or `repo_dirs` must be provided.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `arch` | `list of strings` | *mandatory* | Target CPU architectures (e.g. `["x86_64", "noarch"]`). |
| `releasever` | `string` | *mandatory* | Distribution release version passed to `--releasever` (e.g. `"9"`). |
| `repo_configs` | `list of labels` | `[]` | Template `.repo` or `.conf` files. `@REPO_DIR@` is expanded to the repository directory. |
| `repo_dirs` | `list of labels` | `[]` | Directory artifacts containing `.repo` files (e.g. extracted via `rpm_extract` or container image extraction). `@REPO_DIR@` is expanded to the repository directory. |
| `repo_files` | `list of labels` | `[]` | Repository files (repodata XMLs, signatures). |
| `forcearch` | `string` | `""` | Forced solver architecture. Defaults to first non-noarch entry in `arch`. |
| `nobest` | `bool` | `False` | Allow older candidates when newest requested package cannot be installed. |
| `install_weak_deps` | `bool` | `True` | Install weak/recommended dependencies. |
| `install_langs` | `string` | `""` | Language locales to install/keep (`install_langs=` in `dnf.conf` and `--setopt=install_langs=...` in preamble). |
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
