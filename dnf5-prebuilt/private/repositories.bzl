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

def _dnf5_lock_hub_repository_impl(rctx):
    rctx.file("BUILD.bazel", rctx.attr.build_content)
    rctx.file("defs.bzl", rctx.attr.defs_content)
    for path, content in rctx.attr.package_build_files.items():
        rctx.file(path, content)

dnf5_lock_hub_repository = repository_rule(
    implementation = _dnf5_lock_hub_repository_impl,
    doc = "Exposes RPM targets in topological install_order from a parsed lockfile.",
    attrs = {
        "build_content": attr.string(mandatory = True),
        "defs_content": attr.string(mandatory = True),
        "package_build_files": attr.string_dict(doc = "Relative path -> BUILD.bazel content for subpackages"),
    },
)

_PACKAGE_METADATA_BZL = str(Label("@package_metadata//rules:package_metadata.bzl"))
_INTEGRITY_BZL = str(Label("@package_metadata//attributes:integrity.bzl"))

def _dnf5_rpm_repository_impl(rctx):
    output_path = "file/" + rctx.attr.downloaded_file_path
    rctx.download(
        url = rctx.attr.urls,
        output = output_path,
        integrity = rctx.attr.integrity,
    )

    rctx.file("REPO.bazel", 'repo(default_package_metadata = ["//:package_metadata"])\n')

    build_content = """\
load({package_metadata_bzl}, "package_metadata")
load({integrity_bzl}, "integrity")

package(default_visibility = ["//visibility:public"])

package_metadata(
    name = "package_metadata",
    attributes = [":integrity"],
    purl = {purl},
)

integrity(
    name = "integrity",
    values = [{integrity}],
)

alias(
    name = "file",
    actual = "//file:file",
)
""".format(
        package_metadata_bzl = repr(_PACKAGE_METADATA_BZL),
        integrity_bzl = repr(_INTEGRITY_BZL),
        purl = repr(rctx.attr.purl),
        integrity = repr(rctx.attr.integrity),
    )

    rctx.file("BUILD.bazel", build_content)

    file_build_content = """\
package(default_visibility = ["//visibility:public"])

exports_files([{filename}])

filegroup(
    name = "file",
    srcs = [{filename}],
)
""".format(
        filename = repr(rctx.attr.downloaded_file_path),
    )
    rctx.file("file/BUILD.bazel", file_build_content)

dnf5_rpm_repository = repository_rule(
    implementation = _dnf5_rpm_repository_impl,
    doc = "Downloads one RPM package and annotates it with supply-chain package_metadata.",
    attrs = {
        "downloaded_file_path": attr.string(mandatory = True),
        "integrity": attr.string(mandatory = True),
        "purl": attr.string(mandatory = True),
        "urls": attr.string_list(mandatory = True),
    },
)
