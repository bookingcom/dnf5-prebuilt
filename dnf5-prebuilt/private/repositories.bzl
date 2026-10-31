"""Repository rules fetching prebuilt dnf5 distributions."""

load(":platforms.bzl", "PLATFORMS")

_DIST_BUILD = """\
load("@dnf5-prebuilt//dnf5-prebuilt:toolchain.bzl", "dnf5_toolchain")

package(default_visibility = ["//visibility:public"])

exports_files(["bin/dnf5", "bin/rpm"])

filegroup(
    name = "files",
    srcs = glob(["**"], exclude = ["BUILD.bazel", "REPO.bazel"]),
)

dnf5_toolchain(
    name = "dnf5_toolchain",
    dnf5 = "bin/dnf5",
    rpm = "bin/rpm",
    files = [":files"],
    version = "{version}",
)
"""

def _dnf5_dist_repository_impl(rctx):
    rctx.download_and_extract(
        url = rctx.attr.urls,
        integrity = rctx.attr.integrity,
        stripPrefix = "dnf5",
    )
    rctx.file("BUILD.bazel", _DIST_BUILD.format(version = rctx.attr.version))

dnf5_dist_repository = repository_rule(
    implementation = _dnf5_dist_repository_impl,
    doc = "Downloads one prebuilt dnf5 distribution archive.",
    attrs = {
        "integrity": attr.string(doc = "SRI hash of the archive; empty only for local testing."),
        "urls": attr.string_list(mandatory = True),
        "version": attr.string(mandatory = True),
    },
)

def _dnf5_toolchains_repository_impl(rctx):
    content = []
    for platform in rctx.attr.platforms:
        content.append("""\
toolchain(
    name = "{platform}_toolchain",
    exec_compatible_with = {constraints},
    toolchain = "@{repo}//:dnf5_toolchain",
    toolchain_type = "@dnf5-prebuilt//dnf5-prebuilt:toolchain_type",
)
""".format(
            platform = platform,
            constraints = repr(PLATFORMS[platform]),
            repo = rctx.attr.dist_repos[platform],
        ))
    rctx.file("BUILD.bazel", "\n".join(content))

dnf5_toolchains_repository = repository_rule(
    implementation = _dnf5_toolchains_repository_impl,
    doc = "Declares one toolchain per prebuilt dnf5 distribution.",
    attrs = {
        "dist_repos": attr.string_dict(doc = "platform -> name of its dnf5_dist_repository"),
        "platforms": attr.string_list(),
    },
)
