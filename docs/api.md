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
rpm_layer(name, rpms, rpmdb = None, compress = None, out = None, gpgcheck = False, gpg_keys = [], **kwargs)
```

Macro that assembles RPM packages into an OCI container layer tarball using a deterministic, multi-pass pipeline:
1. **GPG Signature Validation** (when `gpgcheck = True`): Creates a Bazel action producing the GPG keystore directory used by dnf5/rpm, runs one verification action per target RPM against the keystore, and makes the subsequent merging action depend on these validations.
2. **Streaming Extraction and Merging**: Merges all RPMs into an uncompressed tar archive using `bsdtar` in memory without unpacking to disk.
3. **Deduplication**: Deduplicates file and directory paths in the tar archive, keeping the last occurrence to match installation order.
4. **RPM Database Injection** (optional): Injects an updated SQLite `rpmdb` under `/var/lib/rpm/rpmdb.sqlite`.
5. **Compression** (optional): Compresses the layer archive using `gzip` or `zstd`.

#### Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `rpms` | `list of labels` | *mandatory* | List of RPM package files to merge into the layer. |
| `rpmdb` | `label` | `None` | Optional updated SQLite `rpmdb` database file to inject into `/var/lib/rpm/rpmdb.sqlite`. |
| `compress` | `string` | `None` | Optional compression format: `"gzip"` (`.tar.gz`) or `"zstd"` (`.tar.zst`). Uncompressed tar when omitted. |
| `out` | `string` | `None` | Optional explicit output filename. Defaults to `<name>.tar` or `<name>.tar.{gz,zst}`. |
| `gpgcheck` | `bool` | `False` | When `True`, enables hermetic GPG signature validation for all RPM packages prior to archive creation. |
| `gpg_keys` | `list of labels` | `[]` | Optional list of GPG public key files (`.key`, `.asc`, `RPM-GPG-KEY-*`) imported into the keystore. |
| `**kwargs` | `dict` | | Common rule attributes (e.g. `visibility`, `tags`). |

#### Example

```starlark
rpm_layer(
    name = "curl_layer",
    gpgcheck = True,
    rpmdb = ":base_with_curl_rpmdb",
    rpms = [
        "@libcurl_rpm//file",
        "@curl_rpm//file",
    ],
    compress = "gzip",
)
```

---

### `rpm_merge`

```starlark
rpm_merge(name, rpms, gpgcheck = False, rpmdb = None, gpg_keys = [], out = None)
```

Rule that merges RPM packages into an uncompressed tar archive using `bsdtar`.

When `gpgcheck = True`, creates a GPG keystore action (`RpmGpgKeystore`) producing the keystore directory, one verification action per target RPM (`RpmGpgVerify`), and wires them as inputs to the `bsdtar` merging action (`RpmMerge`).

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `rpms` | `list of labels` | *mandatory* | RPM package files (`.rpm`) to extract and merge. |
| `gpgcheck` | `bool` | `False` | Enable GPG signature validation of all RPMs. |
| `rpmdb` | `label` | `None` | Optional rpmdb SQLite file containing GPG public keys. |
| `gpg_keys` | `list of labels` | `[]` | Optional GPG public key files. |
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

Rule that compresses an uncompressed tar archive using `bsdtar` with `gzip` or `zstd`, stripping non-deterministic timestamps.

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
rpm_lock(name, packages, config = None, base_rpmdb = None, arch = ["x86_64", "noarch"], releasever = None, repo_configs = [], repo_files = [], exclude = [], out = None, ...)
```

Rule and executable that resolves dependencies using `dnf5` and generates a hermetic JSON lockfile. Supports multi-layer dependency solving on top of an existing container `base_rpmdb`.

Running `bazel run <target>` updates the lockfile in the source tree.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `packages` | `list of strings` | *mandatory* | List of package specs to resolve (names, NEVRAs, provides). |
| `config` | `label` | `None` | Optional pre-rendered `dnf_config` target. |
| `base_rpmdb` | `label` | `None` | Optional base `rpmdb.sqlite` with already installed packages. |
| `arch` | `list of strings` | `["x86_64", "noarch"]` | Target CPU architectures to resolve for. |
| `releasever` | `string` | `None` | Distribution release version (e.g. `"9"`). |
| `forcearch` | `string` | `""` | Override architecture passed to `--forcearch`. |
| `nobest` | `bool` | `False` | Allow older package candidates (`--no-best`). |
| `install_weak_deps` | `bool` | `True` | Include weak/recommended dependencies. |
| `exclude` | `list of strings` | `[]` | Package names or NEVRA globs to exclude. |
| `repo_configs` | `list of labels` | `[]` | `.repo` configuration files. |
| `repo_files` | `list of labels` | `[]` | Repository metadata files (repodata XMLs). |
| `out` | `output` | `None` | Explicit output file. Defaults to `<name>.lock.json`. |

#### Lockfile Schema

The generated JSON lockfile contains:
- `version`: Lockfile schema version (currently `1`).
- `arch`: Target architecture list.
- `requested`: Array of requested package names.
- `install_order`: Array of package names in topological installation order as dnf5/rpm would install them.
- `order`: Alias for `install_order`.
- `packages`: Array of package objects, each with:
  - `name`: Package name.
  - `version`: Version-release (EVR).
  - `arch`: Architecture.
  - `nevra`: Canonical NEVRA string.
  - `url`: Download URL.
  - `integrity`: Subresource Integrity string (`sha256-<base64>`).
  - `checksum`: Hexadecimal SHA-256 checksum.
  - `dependencies`: List of dependency package names in the closure.
  - `has_preinstall_script` (optional): `true` if the RPM package includes `%pre` install scripts.
  - `has_postinstall_script` (optional): `true` if the RPM package includes `%post` install scripts.

---

### `dnf_config`

```starlark
dnf_config(name, repo_configs, repo_files = [], releasever = "9", arch = ["x86_64", "noarch"], ...)
```

Rule that renders a hermetic `dnf.conf` and repository drop-ins under `repos.d/`, generating a `DnfConfigInfo` provider and preamble argument file pinning dnf5 to the hermetic sandbox.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `repo_configs` | `list of labels` | *mandatory* | Template `.repo` or `.conf` files. `@REPO_DIR@` is expanded to the repository directory. |
| `repo_files` | `list of labels` | `[]` | Repository files (repodata, RPMs). |
| `releasever` | `string` | *mandatory* | Release version passed to `--releasever`. |
| `arch` | `list of strings` | `["x86_64", "noarch"]` | Target CPU architectures. |
| `forcearch` | `string` | `""` | Forced solver architecture. |
| `nobest` | `bool` | `False` | Allow older candidates. |
| `install_weak_deps` | `bool` | `True` | Install weak/recommended dependencies. |
| `vars` | `dict of strings` | `{}` | Custom variables passed via `--setvar=NAME=VALUE`. |

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
| `rpms` | `list of labels` | *mandatory* | RPM package files to record in the database. |
| `base_rpmdb` | `label` | `None` | Optional base `rpmdb.sqlite` to record packages on top of. |
| `out` | `output` | `None` | Output file name. Defaults to `<name>/rpmdb.sqlite`. |

---

## Toolchains and Providers

### `dnf5_toolchain`

```starlark
dnf5_toolchain(name, dnf5, rpm = None, files = [], version = "")
```

Rule defining a dnf5 toolchain resolved for an execution platform.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Toolchain rule name. |
| `dnf5` | `label` | *mandatory* | Path to `bin/dnf5` launcher. |
| `rpm` | `label` | `None` | Optional path to `bin/rpm` launcher. |
| `files` | `list of labels` | `[]` | Complete distribution files. |
| `version` | `string` | `""` | Toolchain distribution version string. |

---

### `current_dnf5_toolchain`

```starlark
current_dnf5_toolchain(name, binary = "dnf5")
```

Rule exposing the resolved launcher (`dnf5` or `rpm`) for the execution platform as an executable target with runfiles.

#### Attributes

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | *mandatory* | Target name. |
| `binary` | `string` | `"dnf5"` | Binary to resolve: `"dnf5"` or `"rpm"`. |

---

### `Dnf5Info`

Provider returned by `dnf5_toolchain` with fields:
- `dnf5`: `File` pointing to `bin/dnf5`.
- `rpm`: `File` pointing to `bin/rpm` (optional).
- `files`: `depset of File` with the entire distribution.
- `version`: Distribution version string.

---

## Bzlmod Extension

### `dnf5`

Module extension in `@dnf5-prebuilt//dnf5-prebuilt:extensions.bzl`.

```starlark
dnf5 = use_extension("@dnf5-prebuilt//dnf5-prebuilt:extensions.bzl", "dnf5")
dnf5.toolchains(name = "dnf5", version = "5.4.6.0")
use_repo(dnf5, "dnf5_toolchains")

register_toolchains("@dnf5_toolchains//:all")
```

Fetches hermetic prebuilt distributions for Linux (`amd64`, `arm64`) and macOS (`amd64`, `arm64`). Override with `--repo_env=DNF5_PREBUILT_DIST_DIR=/path` for local testing.
