# Converting and Merging RPMs into OCI Tar Layers

This document explains how to convert RPM packages directly into standard tar
archives and merge multiple RPMs into a single OCI container layer using
`bsdtar` (from `@tar.bzl` / `libarchive`), without requiring Docker, root
privileges, or intermediate extraction to disk.

---

## Background

When assembling minimal container images (for example using
[`rules_oci`](https://github.com/bazel-contrib/rules_oci) in Bazel), each layer
is typically provided as a tar archive (`.tar` or `.tar.gz`).

Traditional workflows to create a layer from RPM packages often use Docker
builds, `rpm2cpio | cpio -idmv`, or `rpm --installroot`, which unpack every
file onto the filesystem before packaging them into a tar. This approach has
several drawbacks:
- It requires disk I/O proportional to the uncompressed size.
- Hard links, special permissions, and directory modes can be modified or lost
  if the build environment lacks root / user namespace capabilities.
- Non-deterministic timestamps and ownerships leak into the layer.

---

## Direct Multi-RPM Streaming with `bsdtar`

`libarchive` (and its CLI `bsdtar`) includes a native RPM format parser. In
`bsdtar`, prefixing an input filename with `@` instructs the tool to read
entries directly from within that archive:

```bash
# Convert a single RPM to a tarball
bsdtar -cf pkg.tar @pkg.rpm

# Merge multiple RPMs directly into a single layer tar
bsdtar -cf layer.tar @pkg1.rpm @pkg2.rpm @pkg3.rpm
```

### Key Capabilities

1. **Zero Intermediate Extraction**:
   Payloads are streamed directly from the RPM's internal payload (typically
   `cpio` compressed with `zstd` or `xz`) into the tar structure in memory and
   piped directly to the output.
2. **Hard Link and Symlink Preservation**:
   Hard links across files within the RPMs (such as timezone files in
   `tzdata` or binaries in `coreutils`) are preserved as standard tar hard-link
   entries (`link to ...`).
3. **Multi-Archive Merging**:
   Any number of RPMs can be merged in one pass. Later archives in the argument
   list overwrite earlier files with the same path, matching package
   installation ordering.

---

## Deterministic and Reproducible Layers for OCI

For reproducible container builds, use `bsdtar` normalization flags:

```bash
bsdtar -cf layer.tar \
  --numeric-owner \
  --uid 0 --gid 0 \
  --uname root --gname root \
  --mtime "@0" \
  @pkg1.rpm @pkg2.rpm ...
```

- `--numeric-owner`: Ensures numeric UID/GID are stored in standard tar headers.
- `--uid 0 --gid 0` / `--uname root --gname root`: Normalizes file ownership to
  `root:root`.
- `--mtime "@0"`: Normalizes file modification times to the UNIX epoch
  (`1970-01-01 00:00:00 UTC`), ensuring identical byte-for-byte layer digests.

---

## Compression Options

Depending on how your OCI toolchain consumes layers:

```bash
# Uncompressed tar (default for rules_oci layer inputs)
bsdtar -cf layer.tar @pkgs/*.rpm

# Gzip compressed tar (.tar.gz)
bsdtar -czf layer.tar.gz @pkgs/*.rpm

# Zstandard compressed tar (.tar.zst)
bsdtar --zstd -cf layer.tar.zst @pkgs/*.rpm
```

---

## Alternative Tools in the Repository

1. **`rpm2archive` (`@rpm` / upstream RPM)**:
   - Upstream RPM includes `tools/rpm2archive.cc`.
   - Converts an individual RPM package to `.tar` / `.tgz` using `libarchive`:
     ```bash
     rpm2archive pkg.rpm
     ```
   - *Note*: `rpm2archive` converts one package at a time, whereas `bsdtar` can
     merge an entire dependency closure of 50+ packages into a single tar layer
     in one command.
2. **`rpm --root`**:
   - The prebuilt `rpm` binary in `dnf5-prebuilt` can install packages to an
     alternate root directory:
     ```bash
     rpm --root /tmp/rootfs --nodeps --noscripts -ivh *.rpm
     ```
   - Useful when scriptlets or RPM database state (`/var/lib/rpm`) must be
     generated alongside the files.
