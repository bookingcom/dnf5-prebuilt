"""Public API of dnf5-prebuilt."""

load(
    "//dnf5-prebuilt:toolchain.bzl",
    _Dnf5Info = "Dnf5Info",
    _current_dnf5_toolchain = "current_dnf5_toolchain",
    _dnf5_toolchain = "dnf5_toolchain",
)
load(
    "//dnf5-prebuilt/private:config.bzl",
    _DNF5_PREAMBLE = "DNF5_PREAMBLE",
    _dnf_config = "dnf_config",
)
load("//dnf5-prebuilt/private:lock.bzl", _rpm_lock = "rpm_lock")
load("//dnf5-prebuilt/private:mark.bzl", _rpm_mark = "rpm_mark")
load(
    "//dnf5-prebuilt/private:providers.bzl",
    _DnfConfigInfo = "DnfConfigInfo",
    _RpmLockFileInfo = "RpmLockFileInfo",
)

Dnf5Info = _Dnf5Info
current_dnf5_toolchain = _current_dnf5_toolchain
dnf5_toolchain = _dnf5_toolchain

# Rules that run the dnf5 toolchain (register it first, see README).
DNF5_PREAMBLE = _DNF5_PREAMBLE
DnfConfigInfo = _DnfConfigInfo
RpmLockFileInfo = _RpmLockFileInfo
dnf_config = _dnf_config
rpm_lock = _rpm_lock
rpm_mark = _rpm_mark
