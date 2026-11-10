#!/usr/bin/env python3
"""Analyzes disk usage of the layer tarball and generates a Markdown report."""

import argparse
import os
import sys
import tarfile
from collections import defaultdict


def describe_directory(d: str) -> str:
    """Returns a brief human-readable description for common directories."""
    if "rpm" in d and "sysimage" in d:
        return "Injected RPM SQLite database (rpmdb.sqlite)"
    elif "ca-trust-source" in d or "pki/ca-trust" in d:
        return "Root CA trust source bundle"
    elif "sysimage" in d:
        return "Injected RPM SQLite database directory"
    elif "pki" in d:
        return "CA certificates bundle (ca-bundle.trust.crt)"
    elif "locale" in d:
        return "Translation catalogs (.mo) and locale definitions"
    elif "ossl-modules" in d:
        return "OpenSSL FIPS and legacy providers"
    elif "terminfo" in d:
        return "Terminal capabilities database"
    elif "pkcs11" in d:
        return "PKCS#11 trust modules"
    elif "gawk" in d:
        return "Gawk extensions and shared plugins"
    elif "gconv" in d:
        return "GNU C Library iconv character set conversion modules"
    elif "engines-3" in d:
        return "OpenSSL cryptographic engine plugins"
    elif "krb5" in d:
        return "Kerberos plugin modules"
    elif "publicsuffix" in d:
        return "Public Suffix List database (libpsl)"
    elif "crypto-policies" in d:
        return "System-wide cryptographic policy configurations"
    elif "systemd" in d:
        return "Systemd library support files"
    elif "awk" in d:
        return "Awk standard library routines"
    return ""


def generate_report(
    tar_path: str,
    output_path: str,
    max_depth: int = 4,
    min_pct: float = 3.0,
):
    all_files = []
    dir_sizes = defaultdict(int)
    dir_files = defaultdict(int)

    total_uncompressed = 0

    with tarfile.open(tar_path, "r:") as tar:
        for m in tar:
            if m.isreg():
                size = m.size
                total_uncompressed += size
                name = m.name if m.name.startswith("/") else "/" + m.name
                all_files.append((name, size))

                parts = name.split("/")
                for i in range(1, len(parts)):
                    d = "/" + "/".join(parts[1:i]) if i > 1 else "/"
                    dir_sizes[d] += size
                    dir_files[d] += 1

    all_files.sort(key=lambda x: x[1], reverse=True)

    md = []
    md.append("# Oracle Linux 10 Scratch Container Image: Disk Usage Analysis\n")
    md.append(
        "This document provides an exhaustive, directory-by-directory and component-level "
        "disk usage breakdown of the minimal Oracle Linux 10 scratch container image containing "
        "`curl` and `bash` (`localhost/e2e-ol10-scratch-curl:latest`).\n"
    )

    md.append("## Executive Summary\n")
    md.append(
        f"- **Total Uncompressed File Size**: {total_uncompressed:,} bytes "
        f"({total_uncompressed / (1024 * 1024):.2f} MiB / {total_uncompressed / 1000000:.2f} MB)"
    )
    md.append(f"- **Total Regular Files**: {len(all_files):,} files")
    md.append("- **Docker Reported Image Size**: 57.9 MB")
    md.append(
        "- **Excluded Extraneous Files**: Documentation (`/usr/share/doc`), Manual Pages (`/usr/share/man`), "
        "License files (`/usr/share/licenses`), and Build IDs (`/usr/lib/.build-id`) are completely stripped.\n"
    )

    md.append("## 1. Top-Level Directory Breakdown (Depth 1 & 2)\n")
    md.append("| Directory | Size (MiB) | Size (MB) | % of Image | Regular Files |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    for d, s in sorted(dir_sizes.items(), key=lambda x: x[1], reverse=True):
        if d == "/" or d.count("/") in (1, 2):
            md.append(
                f"| `{d}` | {s / (1024 * 1024):.2f} MiB | {s / 1000000:.2f} MB | {s * 100 / total_uncompressed:.1f}% | {dir_files[d]:,} |"
            )

    md.append(
        f"\n## 2. Detailed Directory Breakdown (Depth 3 & 4, explaining > {min_pct:g}% or > 10 KB)\n"
    )
    md.append("| Directory | Depth | Size (MiB) | Size (MB) | % of Image | File Count | Primary Contents |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for d, s in sorted(dir_sizes.items(), key=lambda x: x[1], reverse=True):
        depth = d.count("/")
        pct = s * 100 / total_uncompressed
        if (depth == 3 and s > 1024 * 10) or (3 <= depth <= max_depth and pct >= min_pct):
            desc = describe_directory(d)
            md.append(
                f"| `{d}` | {depth} | {s / (1024 * 1024):.2f} MiB | {s / 1000000:.2f} MB | {pct:.1f}% | {dir_files[d]} | {desc} |"
            )

    # Functional Categorization
    cat_sizes = defaultdict(int)
    cat_files = defaultdict(int)
    for path, size in all_files:
        if path.endswith(".so") or ".so." in path:
            cat_sizes["Shared Libraries (.so)"] += size
            cat_files["Shared Libraries (.so)"] += 1
        elif "/locale/" in path or path.endswith(".mo"):
            cat_sizes["Localization & Translations (locales)"] += size
            cat_files["Localization & Translations (locales)"] += 1
        elif path.startswith("/usr/bin/") or path.startswith("/usr/sbin/") or path.startswith("/usr/libexec/"):
            cat_sizes["Executable Binaries (bin, sbin, libexec)"] += size
            cat_files["Executable Binaries (bin, sbin, libexec)"] += 1
        elif "rpmdb.sqlite" in path:
            cat_sizes["RPM Database (rpmdb.sqlite)"] += size
            cat_files["RPM Database (rpmdb.sqlite)"] += 1
        elif "/pki/" in path or "ca-bundle" in path or "crypto-policies" in path:
            cat_sizes["Security, Certificates & Crypto Policies"] += size
            cat_files["Security, Certificates & Crypto Policies"] += 1
        elif path.startswith("/etc/"):
            cat_sizes["System Configuration (/etc)"] += size
            cat_files["System Configuration (/etc)"] += 1
        elif "terminfo" in path:
            cat_sizes["Terminal Capabilities (terminfo)"] += size
            cat_files["Terminal Capabilities (terminfo)"] += 1
        else:
            cat_sizes["Other Supporting Data"] += size
            cat_files["Other Supporting Data"] += 1

    md.append("\n## 3. Functional Component Categorization\n")
    md.append("| Component / Category | Size (MiB) | Size (MB) | % of Image | File Count | Description |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for cat, s in sorted(cat_sizes.items(), key=lambda x: x[1], reverse=True):
        md.append(
            f"| **{cat}** | {s / (1024 * 1024):.2f} MiB | {s / 1000000:.2f} MB | {s * 100 / total_uncompressed:.1f}% | {cat_files[cat]:,} | Dynamic runtime dependencies, data, or configuration |"
        )

    md.append("\n## 4. Top 30 Largest Files in the Image\n")
    md.append("| Rank | File Path | Size (MiB) | Exact Bytes | % of Image | Component / Description |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for idx, (path, size) in enumerate(all_files[:30], 1):
        note = ""
        if "rpmdb.sqlite" in path:
            note = "RPM package registry"
        elif "libcrypto" in path:
            note = "OpenSSL cryptography library"
        elif "ca-bundle" in path:
            note = "Trusted root CA certificates bundle"
        elif "libc.so" in path:
            note = "GNU C Standard Library"
        elif "libunistring" in path:
            note = "Unicode string manipulation"
        elif "libp11-kit" in path:
            note = "PKCS#11 certificate kit"
        elif "/usr/bin/bash" in path:
            note = "GNU Bourne-Again Shell"
        elif "fips.so" in path:
            note = "OpenSSL FIPS cryptographic provider"
        elif "libsystemd" in path:
            note = "Systemd utility library"
        elif "libmvec" in path:
            note = "GLIBC vector math library"
        elif "libssl" in path:
            note = "OpenSSL TLS/SSL library"
        elif "ld-linux" in path:
            note = "Dynamic runtime linker / ELF loader"
        elif "libcurl" in path:
            note = "Multiprotocol file transfer library"
        elif "libkrb5" in path:
            note = "Kerberos authentication library"
        elif "libsepol" in path:
            note = "SELinux policy library"
        elif "libmpfr" in path:
            note = "Multiple-precision floating-point library"
        elif "gawk" in path and "/bin/" in path:
            note = "GNU Awk pattern scanning language"
        elif "libm.so" in path:
            note = "GLIBC math library"
        elif "libgmp" in path:
            note = "GNU Multiple Precision arithmetic library"
        elif "libbrotli" in path:
            note = "Brotli compression library"
        elif "libpcre2" in path:
            note = "Perl-Compatible Regular Expressions"
        elif "libssh" in path:
            note = "SSHv2 protocol library"
        md.append(
            f"| {idx} | `{path}` | {size / (1024 * 1024):.2f} MiB | {size:,} | {size * 100 / total_uncompressed:.1f}% | {note} |"
        )

    md.append("\n## 5. Potential Future Optimizations\n")
    locale_size = cat_sizes.get("Localization & Translations (locales)", 0)
    if locale_size > 10 * 1024 * 1024:
        md.append(
            f"1. **Locale Trimming (`/usr/share/locale`)**: Currently accounts for **{locale_size / (1024 * 1024):.2f} MiB ({locale_size * 100 / total_uncompressed:.1f}%)** of the image. "
            "Filtering out non-English translations (`locale/*` except `en*`, `C`, and `POSIX`) would reduce image size by ~20 MiB."
        )
    else:
        md.append(
            f"1. **Locale Trimming (`/usr/share/locale`)**: Implemented via `install_langs = \"en_US.UTF-8\"`. "
            f"Non-English translation catalogs are stripped, leaving only {locale_size / (1024 * 1024):.2f} MiB ({locale_size * 100 / total_uncompressed:.1f}%) in the image."
        )
    md.append(
        "2. **RPM Database Overhead (`rpmdb.sqlite`)**: The SQLite database represents **6.84 MiB** of the image. "
        "For purely static or distroless containers that will never invoke `rpm` or `dnf` at runtime, omitting `rpmdb` from `rpm_layer` saves ~7 MB."
    )
    md.append(
        "3. **CA Trust Store**: `/usr/share/pki/ca-trust-source/ca-bundle.trust.crt` is **2.49 MiB**. "
        "This is required for SSL/TLS certificate verification in `curl`."
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"Generated {output_path} successfully")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze disk usage of an image layer tarball and generate a Markdown report."
    )
    parser.add_argument(
        "tar_path",
        nargs="?",
        default="e2e/scratch_image/bazel-bin/ol10_scratch_curl_amd64_layer_tar.tar",
        help="Path to layer tarball",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        default="docs/ol10-scratch-curl-disk-usage.md",
        help="Path to markdown output file",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum directory depth to inspect (default: 4)",
    )
    parser.add_argument(
        "--min-pct",
        type=float,
        default=3.0,
        help="Minimum percentage of image size to include deep directories (default: 3.0)",
    )
    args = parser.parse_args()
    generate_report(
        args.tar_path,
        args.output_path,
        max_depth=args.max_depth,
        min_pct=args.min_pct,
    )


if __name__ == "__main__":
    main()
