"""Public API of dnf5-prebuilt."""

load(
    "//dnf5-prebuilt:toolchain.bzl",
    _Dnf5Info = "Dnf5Info",
    _current_dnf5_toolchain = "current_dnf5_toolchain",
    _dnf5_toolchain = "dnf5_toolchain",
)
load(
    "//dnf5-prebuilt/private:config.bzl",
    _dnf_config = "dnf_config",
)
load(
    "//dnf5-prebuilt/private:mark.bzl",
    _rpm_mark = "rpm_mark",
)

Dnf5Info = _Dnf5Info
current_dnf5_toolchain = _current_dnf5_toolchain
dnf5_toolchain = _dnf5_toolchain
dnf_config = _dnf_config
rpm_mark = _rpm_mark
