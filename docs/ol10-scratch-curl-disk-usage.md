# Oracle Linux 10 Scratch Container Image: Disk Usage Analysis

This document provides an exhaustive, directory-by-directory and component-level disk usage breakdown of the minimal Oracle Linux 10 scratch container image containing `curl` and `bash` (`localhost/e2e-ol10-scratch-curl:latest`).

## Executive Summary

- **Total Uncompressed File Size**: 79,056,606 bytes (75.39 MiB / 79.06 MB)
- **Total Regular Files**: 1,008 files
- **Docker Reported Image Size**: 80.8 MB
- **Excluded Extraneous Files**: Documentation (`/usr/share/doc`), Manual Pages (`/usr/share/man`), License files (`/usr/share/licenses`), and Build IDs (`/usr/lib/.build-id`) are completely stripped (0 files present).

## 1. Top-Level Directory Breakdown (Depth 1 & 2)

| Directory | Size (MiB) | Size (MB) | % of Image | Regular Files |
| :--- | :--- | :--- | :--- | :--- |
| `/` | 75.39 MiB | 79.06 MB | 100.0% | 1,008 |
| `/usr/lib64` | 31.09 MiB | 32.60 MB | 41.2% | 126 |
| `/usr/share` | 24.11 MiB | 25.28 MB | 32.0% | 589 |
| `/usr/bin` | 9.62 MiB | 10.09 MB | 12.8% | 153 |
| `/usr/lib` | 7.21 MiB | 7.56 MB | 9.6% | 27 |
| `/usr/sbin` | 2.36 MiB | 2.48 MB | 3.1% | 28 |
| `/usr/libexec` | 0.07 MiB | 0.07 MB | 0.1% | 9 |
| `/etc/pki` | 0.03 MiB | 0.03 MB | 0.0% | 12 |
| `/etc/profile.d` | 0.01 MiB | 0.01 MB | 0.0% | 10 |
| `/etc/selinux` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/etc/ssl` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/etc/openldap` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/etc/skel` | 0.00 MiB | 0.00 MB | 0.0% | 3 |
| `/etc/rpm` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/etc/libssh` | 0.00 MiB | 0.00 MB | 0.0% | 2 |
| `/etc/pam.d` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/etc/default` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/var/lib` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/etc/dnf` | 0.00 MiB | 0.00 MB | 0.0% | 1 |
| `/etc/sysconfig` | 0.00 MiB | 0.00 MB | 0.0% | 1 |

## 2. Detailed Directory Breakdown (Depth 3)

| Directory | Size (MiB) | Size (MB) | % of Image | File Count | Primary Contents |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/usr/share/locale` | 21.21 MiB | 22.24 MB | 28.1% | 348 | Translation catalogs (.mo) and locale definitions |
| `/usr/lib/sysimage` | 6.84 MiB | 7.17 MB | 9.1% | 1 | Injected RPM SQLite database (rpmdb.sqlite) |
| `/usr/share/pki` | 2.49 MiB | 2.61 MB | 3.3% | 4 | CA certificates bundle (ca-bundle.trust.crt) |
| `/usr/lib64/ossl-modules` | 1.39 MiB | 1.46 MB | 1.8% | 2 | OpenSSL FIPS and legacy providers |
| `/usr/lib/locale` | 0.35 MiB | 0.37 MB | 0.5% | 12 | Translation catalogs (.mo) and locale definitions |
| `/usr/share/terminfo` | 0.28 MiB | 0.29 MB | 0.4% | 128 | Terminal capabilities database |
| `/usr/lib64/pkcs11` | 0.24 MiB | 0.25 MB | 0.3% | 1 | PKCS#11 trust modules |
| `/usr/lib64/gawk` | 0.20 MiB | 0.21 MB | 0.3% | 12 | Gawk extensions and shared plugins |
| `/usr/lib64/gconv` | 0.14 MiB | 0.15 MB | 0.2% | 9 | GNU C Library iconv character set conversion modules |
| `/usr/lib64/engines-3` | 0.12 MiB | 0.12 MB | 0.2% | 4 | OpenSSL cryptographic engine plugins |
| `/usr/lib64/krb5` | 0.11 MiB | 0.11 MB | 0.1% | 2 | Kerberos plugin modules |
| `/usr/lib64/sasl2` | 0.05 MiB | 0.06 MB | 0.1% | 2 |  |
| `/usr/share/publicsuffix` | 0.05 MiB | 0.05 MB | 0.1% | 1 | Public Suffix List database (libpsl) |
| `/usr/libexec/awk` | 0.03 MiB | 0.03 MB | 0.0% | 2 | Awk standard library routines |
| `/usr/share/awk` | 0.02 MiB | 0.02 MB | 0.0% | 29 | Awk standard library routines |
| `/usr/libexec/p11-kit` | 0.02 MiB | 0.02 MB | 0.0% | 2 |  |
| `/usr/share/zsh` | 0.02 MiB | 0.02 MB | 0.0% | 3 |  |
| `/usr/lib64/security` | 0.02 MiB | 0.02 MB | 0.0% | 1 |  |
| `/usr/share/crypto-policies` | 0.02 MiB | 0.02 MB | 0.0% | 67 | System-wide cryptographic policy configurations |
| `/usr/lib/systemd` | 0.02 MiB | 0.02 MB | 0.0% | 6 | Systemd library support files |
| `/usr/lib64/audit` | 0.01 MiB | 0.02 MB | 0.0% | 1 |  |
| `/usr/libexec/coreutils` | 0.01 MiB | 0.02 MB | 0.0% | 1 |  |
| `/etc/pki/tls` | 0.01 MiB | 0.01 MB | 0.0% | 2 | CA certificates bundle (ca-bundle.trust.crt) |

## 3. Functional Component Categorization

| Component / Category | Size (MiB) | Size (MB) | % of Image | File Count | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Shared Libraries (.so)** | 31.28 MiB | 32.80 MB | 41.5% | 127 | Dynamic runtime dependencies, data, or configuration |
| **Localization & Translations (locales)** | 21.56 MiB | 22.61 MB | 28.6% | 360 | Dynamic runtime dependencies, data, or configuration |
| **Executable Binaries (bin, sbin, libexec)** | 12.03 MiB | 12.62 MB | 16.0% | 189 | Dynamic runtime dependencies, data, or configuration |
| **RPM Database (rpmdb.sqlite)** | 6.84 MiB | 7.17 MB | 9.1% | 1 | Dynamic runtime dependencies, data, or configuration |
| **Security, Certificates & Crypto Policies** | 2.53 MiB | 2.65 MB | 3.4% | 83 | Dynamic runtime dependencies, data, or configuration |
| **System Configuration (/etc)** | 0.73 MiB | 0.77 MB | 1.0% | 61 | Dynamic runtime dependencies, data, or configuration |
| **Terminal Capabilities (terminfo)** | 0.28 MiB | 0.29 MB | 0.4% | 128 | Dynamic runtime dependencies, data, or configuration |
| **Other Supporting Data** | 0.14 MiB | 0.15 MB | 0.2% | 59 | Dynamic runtime dependencies, data, or configuration |

## 4. Top 30 Largest Files in the Image

| Rank | File Path | Size (MiB) | Exact Bytes | % of Image | Component / Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `/usr/lib/sysimage/rpm/rpmdb.sqlite` | 6.84 MiB | 7,172,096 | 9.1% | RPM package registry |
| 2 | `/usr/lib64/libcrypto.so.3.5.8` | 5.38 MiB | 5,644,744 | 7.1% | OpenSSL cryptography library |
| 3 | `/usr/share/pki/ca-trust-source/ca-bundle.trust.p11-kit` | 2.48 MiB | 2,605,280 | 3.3% | Trusted root CA certificates bundle |
| 4 | `/usr/lib64/libc.so.6` | 2.24 MiB | 2,344,040 | 3.0% | GNU C Standard Library |
| 5 | `/usr/lib64/libunistring.so.5.0.0` | 1.68 MiB | 1,764,184 | 2.2% | Unicode string manipulation |
| 6 | `/usr/lib64/libp11-kit.so.0.4.10` | 1.61 MiB | 1,683,088 | 2.1% | PKCS#11 certificate kit |
| 7 | `/usr/bin/bash` | 1.35 MiB | 1,410,456 | 1.8% | GNU Bourne-Again Shell |
| 8 | `/usr/lib64/ossl-modules/fips.so` | 1.28 MiB | 1,337,152 | 1.7% | OpenSSL FIPS cryptographic provider |
| 9 | `/usr/lib64/libsystemd.so.0.40.0` | 1.17 MiB | 1,225,176 | 1.5% | Systemd utility library |
| 10 | `/usr/lib64/libmvec.so.1` | 0.98 MiB | 1,027,688 | 1.3% | GLIBC vector math library |
| 11 | `/usr/lib64/libssl.so.3.5.8` | 0.95 MiB | 990,976 | 1.3% | OpenSSL TLS/SSL library |
| 12 | `/usr/sbin/ldconfig` | 0.90 MiB | 940,304 | 1.2% |  |
| 13 | `/usr/lib64/ld-linux-x86-64.so.2` | 0.90 MiB | 939,560 | 1.2% | Dynamic runtime linker / ELF loader |
| 14 | `/usr/lib64/libcurl.so.4.8.0` | 0.82 MiB | 857,192 | 1.1% | Multiprotocol file transfer library |
| 15 | `/usr/lib64/libkrb5.so.3.3` | 0.80 MiB | 840,808 | 1.1% | Kerberos authentication library |
| 16 | `/usr/lib64/libsepol.so.2` | 0.79 MiB | 831,368 | 1.1% | SELinux policy library |
| 17 | `/usr/lib64/libmpfr.so.6.2.1` | 0.75 MiB | 783,128 | 1.0% | Multiple-precision floating-point library |
| 18 | `/usr/bin/gawk` | 0.73 MiB | 763,800 | 1.0% | GNU Awk pattern scanning language |
| 19 | `/usr/lib64/libm.so.6` | 0.69 MiB | 720,632 | 0.9% | GLIBC math library |
| 20 | `/etc/services` | 0.67 MiB | 701,707 | 0.9% |  |
| 21 | `/usr/lib64/libgmp.so.10.4.1` | 0.65 MiB | 686,288 | 0.9% | GNU Multiple Precision arithmetic library |
| 22 | `/usr/lib64/libbrotlienc.so.1.1.0` | 0.64 MiB | 668,968 | 0.8% | Brotli compression library |
| 23 | `/usr/lib64/libpcre2-8.so.0.13.0` | 0.63 MiB | 661,472 | 0.8% | Perl-Compatible Regular Expressions |
| 24 | `/usr/lib64/libssh.so.4.11.0` | 0.61 MiB | 641,960 | 0.8% | SSHv2 protocol library |
| 25 | `/usr/share/locale/uk/LC_MESSAGES/coreutils.mo` | 0.47 MiB | 492,949 | 0.6% |  |
| 26 | `/usr/share/locale/bg/LC_MESSAGES/coreutils.mo` | 0.45 MiB | 476,803 | 0.6% |  |
| 27 | `/usr/lib64/libnss_systemd.so.2` | 0.44 MiB | 457,800 | 0.6% |  |
| 28 | `/usr/share/locale/sr/LC_MESSAGES/coreutils.mo` | 0.43 MiB | 447,934 | 0.6% |  |
| 29 | `/usr/share/locale/ru/LC_MESSAGES/coreutils.mo` | 0.42 MiB | 438,999 | 0.6% |  |
| 30 | `/usr/lib64/libldap.so.2.0.200` | 0.40 MiB | 417,864 | 0.5% |  |

## 5. Potential Future Optimizations

1. **Locale Trimming (`/usr/share/locale`)**: Currently accounts for **21.21 MiB (28.1%)** of the image. Filtering out non-English translations (`locale/*` except `en*`, `C`, and `POSIX`) would reduce image size by ~20 MiB.
2. **RPM Database Overhead (`rpmdb.sqlite`)**: The SQLite database represents **6.84 MiB (9.1%)** of the image. For purely static or distroless containers that will never invoke `rpm` or `dnf` at runtime, omitting `rpmdb` from `rpm_layer` saves ~7 MB.
3. **CA Trust Store**: `/usr/share/pki/ca-trust-source/ca-bundle.trust.crt` is **2.49 MiB (3.3%)**. This is required for SSL/TLS certificate verification in `curl`.
