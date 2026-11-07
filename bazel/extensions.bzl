"""Module extensions for building dnf5 from source (private API)."""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# Upstream release built by this repository.
DNF5_VERSION = "5.4.6.0"
DNF5_SHA256 = "242f0e775bc8e1017a5bfec841c776beafa7ea6b5bd2e4d7bc0ff9d7c57998f3"

# Fixes applied on top of the release (git format-patch output, see
# bazel/dnf5/patches). Keep them upstreamable.
DNF5_PATCHES = [
    "0001-Disambiguate-includes-that-depend-on-the-include-sea.patch",
    "0002-Include-the-standard-headers-that-are-used.patch",
    "0003-libdnf5-cli-fix-the-build-with-libc.patch",
    "0004-module-use-strictly-POSIX-extended-regular-expressio.patch",
    "0005-utils-report-arm64-Macs-as-aarch64-in-detect_arch.patch",
    "0006-repo-let-a-caller-fill-System-from-a-testcase-and-re.patch",
]

def _dnf5_extension_impl(mctx):
    http_archive(
        name = "dnf5",
        build_file = Label("//bazel/dnf5:dnf5.BUILD.bazel"),
        patch_args = ["-p1"],
        patches = [Label("//bazel/dnf5:patches/" + p) for p in DNF5_PATCHES],
        sha256 = DNF5_SHA256,
        strip_prefix = "dnf5-%s" % DNF5_VERSION,
        urls = ["https://github.com/rpm-software-management/dnf5/archive/refs/tags/%s.tar.gz" % DNF5_VERSION],
    )
    return mctx.extension_metadata(
        reproducible = True,
        root_module_direct_deps = [],
        root_module_direct_dev_deps = ["dnf5"],
    )

dnf5_extension = module_extension(
    implementation = _dnf5_extension_impl,
    doc = "Fetches the upstream dnf5 sources (@dnf5) with the Bazel overlay from //bazel/dnf5.",
)
