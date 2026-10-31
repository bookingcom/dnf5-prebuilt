# RPM Dependency Trees, URL Resolution, and Integrity Extraction

This document describes how to resolve RPM dependency trees as structured JSON
or ASCII graphs, resolve package download URLs in $O(1)$, and extract cryptographic
SHA-256 package checksums directly from repodata XML using `dnf5` and `rpm`
without Docker or root privileges.

---

## 1. Recursive Capability Resolution & Dependency Trees

In DNF 4, `repoquery --resolve` was commonly used for recursive dependency
lookups. In DNF 5, `--resolve` was removed from `repoquery`. The modern DNF 5
equivalent for capability-based recursive resolution is:

```bash
dnf5 repoquery --arch=x86_64 --providers-of=requires --recursive <pkg>
```

### Batch Metadata Query in $O(1)$

To build a full hierarchical dependency tree (with cycle detection and
explicit versus capability dependencies), query package metadata in a single
pass using `--queryformat`:

```bash
dnf5 repoquery -C \
  --queryformat="NAME:%{name}\nPROVIDES:\n%{provides}\nREQUIRES:\n%{regular_requires}\n" \
  <pkgs...>
```

- Each package provides a list of capabilities (e.g., `libcurl.so.4()(64bit)`,
  `config(curl) = 8.12.1`, `curl = 8.12.1-4.el10_2.7`).
- Each package requires capabilities (e.g., `libc.so.6(GLIBC_2.38)(64bit)`).
- By matching requirements to package providers in the closure, an in-memory graph
  can be constructed and serialized as:
  - **ASCII Tree**: indented visual hierarchy with cycle indicators (`(*)`).
  - **JSON Hierarchy**: tree of objects containing `name`, `evr`, `arch`, and
    nested `dependencies`.

---

## 2. Resolving Download URLs in $O(1)$

DNF 5 provides native URL resolution via `dnf5 download --url`:

### Full Transitive Closure
To resolve all package URLs needed to install a package from scratch
(independent of what is currently installed):

```bash
dnf5 download -C -q --arch=x86_64 --url --resolve --alldeps <pkg>
```

This returns the exact URLs for the entire closure (for example, 70 packages
for `curl`).

### Incremental Closure (Delta over Existing Root)
To resolve only missing packages over an existing installed root (such as a
base OS image or existing rpmdb):

```bash
dnf5 download -C -q --arch=x86_64 --url --resolve \
  --installroot=/path/to/rootfs <pkg>
```

Packages already satisfied by the root's RPM database (`/var/lib/rpm`) are
omitted, leaving only the delta to download.

---

## 3. Cryptographic Integrity Extraction in $O(1)$

DNF 5 caches repository repodata under `/var/cache/libdnf5/` (or a custom
directory specified with `--setopt=cachedir=...`).

The authoritative SHA-256 integrity hash for every package in a repository is
recorded in the repository's `primary.xml.gz` metadata file:

```xml
<package type="rpm">
  <name>curl</name>
  <checksum type="sha256" pkgid="YES">e66b8cf01b6ba40409a8ecf248e36d4f9540bca803716d0046e7f80ea5d1ff3d</checksum>
  <location href="getPackage/curl-8.12.1-4.el10_2.7.x86_64.rpm"/>
</package>
```

### Single-Pass Streaming Extraction
Rather than downloading packages individually to compute hashes or querying
them via remote network requests, parse `repodata/*-primary.xml.gz` directly.

A lightweight streaming XML parser (such as Python's `xml.etree.ElementTree.iterparse`
with `gzip`) can map every package filename/href to its canonical SHA-256 hash
in single-digit seconds across repositories containing 10,000+ packages:

```python
import gzip
import xml.etree.ElementTree as ET

def load_repodata_checksums(primary_xml_gz_path):
    checksums = {}
    with gzip.open(primary_xml_gz_path, "rb") as f:
        for event, elem in ET.iterparse(f, events=("end",)):
            if elem.tag.endswith("package"):
                checksum_elem = elem.find("{http://linux.duke.edu/metadata/common}checksum")
                location_elem = elem.find("{http://linux.duke.edu/metadata/common}location")
                if checksum_elem is not None and location_elem is not None:
                    href = location_elem.attrib.get("href", "")
                    checksums[href.split("/")[-1]] = checksum_elem.text
                elem.clear()
    return checksums
```

Combining the resolved URLs from `dnf5 download --url` with the repodata
checksum map produces a complete Bazel manifest (`url` + `sha256` integrity)
instantly:

```json
{
  "name": "curl",
  "version": "8.12.1-4.el10_2.7",
  "arch": "x86_64",
  "url": "https://yum.oracle.com/repo/OracleLinux/OL10/baseos/latest/x86_64/getPackage/curl-8.12.1-4.el10_2.7.x86_64.rpm",
  "sha256": "e66b8cf01b6ba40409a8ecf248e36d4f9540bca803716d0046e7f80ea5d1ff3d"
}
```

---

## 4. End-to-End Workflow with OCI Layers

By pairing dependency resolution with `bsdtar` streaming:

1. **Resolve**: Use `dnf5 download -q --url --resolve --alldeps <pkg>` and
   `primary.xml.gz` to declare hermetic repository downloads in Bazel rules.
2. **Download**: Fetch packages deterministically via Bazel `http_file` or
   custom repository rules with known SHA-256 checksums.
3. **Assemble**: Merge the downloaded RPMs directly into an OCI container
   layer tarball using:
   ```bash
   bsdtar -cf layer.tar @pkg1.rpm @pkg2.rpm ...
   ```
   (See [Converting and Merging RPMs into OCI Tar Layers](rpm-to-oci-layer.md)).
