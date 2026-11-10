"""Implementation of the multi-pass rpm_layer rule and macro."""

load("@bazel_lib//lib:utils.bzl", "propagate_common_rule_attributes")
load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN")
load("//dnf5-prebuilt/private:gpg.bzl", "gpg_attrs", "verify_rpms_gpg")

TAR_TOOLCHAIN_TYPE = "@tar.bzl//tar/toolchain:type"

DOCS_PATTERNS = [
    "*/share/doc/*",
    "*/share/doc",
    "*/share/info/*",
    "*/share/info",
]

MAN_PATTERNS = [
    "*/share/man/*",
    "*/share/man",
]

LICENSES_PATTERNS = [
    "*/share/licenses/*",
    "*/share/licenses",
]

BUILD_ID_PATTERNS = [
    "*/.build-id/*",
    "*/.build-id",
]

def _rpm_merge_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out or (ctx.label.name + ".tar"))
    tar_toolchain = ctx.toolchains[TAR_TOOLCHAIN_TYPE]
    bsdtar = tar_toolchain.tarinfo.binary

    extra_inputs = verify_rpms_gpg(ctx)

    args = ctx.actions.args()
    args.add("-cf", out)
    args.add("--format=pax")
    args.add("--numeric-owner")
    args.add("--owner=0")
    args.add("--group=0")
    for pattern in ctx.attr.exclude_patterns:
        args.add("--exclude=" + pattern)
    for rpm in ctx.files.rpms:
        args.add("@" + rpm.path)

    ctx.actions.run(
        mnemonic = "RpmMerge",
        progress_message = "Merging RPMs into uncompressed archive %s" % out.short_path,
        executable = bsdtar,
        arguments = [args],
        inputs = depset(ctx.files.rpms + extra_inputs, transitive = [tar_toolchain.default.files]),
        outputs = [out],
        env = tar_toolchain.tarinfo.default_env,
    )
    return [DefaultInfo(files = depset([out]))]

rpm_merge = rule(
    doc = "Merges RPM packages into an uncompressed tar archive using bsdtar.",
    implementation = _rpm_merge_impl,
    attrs = gpg_attrs() | {
        "exclude_patterns": attr.string_list(
            default = [],
            doc = "Glob patterns to exclude when extracting RPMs with bsdtar.",
        ),
        "out": attr.string(doc = "Optional output file name. Defaults to <name>.tar."),
        "rpms": attr.label_list(
            allow_files = [".rpm"],
            mandatory = True,
            doc = "RPM package files to extract and merge.",
        ),
    },
    toolchains = [TAR_TOOLCHAIN_TYPE, DNF5_TOOLCHAIN],
)

def _tar_dedup_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out or (ctx.label.name + ".tar"))
    args = ctx.actions.args()
    args.add("--input", ctx.file.src)
    args.add("--output", out)
    if ctx.attr.install_langs:
        args.add("--install-langs", ctx.attr.install_langs)

    ctx.actions.run(
        mnemonic = "TarDedup",
        progress_message = "Deduplicating tar archive %s" % out.short_path,
        executable = ctx.executable._tool,
        arguments = [args],
        inputs = [ctx.file.src],
        outputs = [out],
    )
    return [DefaultInfo(files = depset([out]))]

tar_dedup = rule(
    doc = "Deduplicates tar directory entries and files, keeping the last occurrence and filtering locales.",
    implementation = _tar_dedup_impl,
    attrs = {
        "install_langs": attr.string(
            default = "",
            doc = "Language locales to keep (e.g. 'en_US.UTF-8'), filtering non-matching locale files.",
        ),
        "out": attr.string(doc = "Optional output file name. Defaults to <name>.tar."),
        "src": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "Input uncompressed tar archive.",
        ),
        "_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:tar_dedup"),
            executable = True,
            cfg = "exec",
            doc = "Internal tar deduplication tool.",
        ),
    },
)

def _rpmdb_inject_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out or (ctx.label.name + ".tar"))
    args = ctx.actions.args()
    args.add("--input", ctx.file.src)
    args.add("--rpmdb", ctx.file.rpmdb)
    args.add("--output", out)

    ctx.actions.run(
        mnemonic = "RpmdbInject",
        progress_message = "Injecting rpmdb into tar archive %s" % out.short_path,
        executable = ctx.executable._tool,
        arguments = [args],
        inputs = [ctx.file.src, ctx.file.rpmdb],
        outputs = [out],
    )
    return [DefaultInfo(files = depset([out]))]

rpmdb_inject = rule(
    doc = "Injects an rpmdb file into a tar archive under /var/lib/rpm/rpmdb.sqlite.",
    implementation = _rpmdb_inject_impl,
    attrs = {
        "out": attr.string(doc = "Optional output file name. Defaults to <name>.tar."),
        "rpmdb": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "SQLite rpmdb file to inject.",
        ),
        "src": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "Input tar archive.",
        ),
        "_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:tar_inject_rpmdb"),
            executable = True,
            cfg = "exec",
            doc = "Internal rpmdb injection tool.",
        ),
    },
)

def _tar_compress_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out or ctx.label.name)
    tar_toolchain = ctx.toolchains[TAR_TOOLCHAIN_TYPE]
    bsdtar = tar_toolchain.tarinfo.binary

    args = ctx.actions.args()
    args.add("-cf", out)
    if ctx.attr.compress == "gzip":
        args.add("--gzip")
        args.add("--options=gzip:!timestamp")
    elif ctx.attr.compress == "zstd":
        args.add("--zstd")
    args.add("@" + ctx.file.src.path)

    ctx.actions.run(
        mnemonic = "TarCompress",
        progress_message = "Compressing tar archive %s" % out.short_path,
        executable = bsdtar,
        arguments = [args],
        inputs = depset([ctx.file.src], transitive = [tar_toolchain.default.files]),
        outputs = [out],
        env = tar_toolchain.tarinfo.default_env,
    )
    return [DefaultInfo(files = depset([out]))]

tar_compress = rule(
    doc = "Compresses a tar archive using bsdtar with gzip or zstd.",
    implementation = _tar_compress_impl,
    attrs = {
        "compress": attr.string(
            mandatory = True,
            values = ["gzip", "zstd"],
            doc = "Compression format ('gzip' or 'zstd').",
        ),
        "out": attr.string(doc = "Optional output file name. Defaults to <name>."),
        "src": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "Input tar archive to compress.",
        ),
    },
    toolchains = [TAR_TOOLCHAIN_TYPE],
)

def rpm_layer(
        name,
        rpms,
        rpmdb = None,
        compress = None,
        out = None,
        gpgcheck = False,
        gpgkeys = [],
        exclude_docs = True,
        exclude_man = True,
        exclude_licenses = True,
        exclude_build_id = True,
        exclude_patterns = [],
        install_langs = None,
        **kwargs):
    """Assembles RPM packages into an OCI container layer tarball.

    Implements a multi-pass approach:
    1. Merge all RPMs with bsdtar into an uncompressed archive (validating GPG signatures if gpgcheck is enabled),
       excluding docs, man pages, license files, and build-id by default for minimal container layers.
    2. Iterate over the entries and deduplicate directory and file paths with Python, optionally filtering
       locales if install_langs is specified (mimicking DNF --setopt=install_langs=... and RPM %_install_langs).
    3. Inject rpmdb into the archive (if rpmdb is specified).
    4. Compress the layer (if compress='gzip' or 'zstd' is specified).

    Args:
      name: Target name.
      rpms: List of RPM package files.
      rpmdb: Optional updated rpmdb SQLite file.
      compress: Optional compression algorithm ('gzip' or 'zstd').
      out: Optional explicit output file name.
      gpgcheck: Optional boolean flag to enable GPG signature validation of RPMs.
      gpgkeys: Optional list of GPG public key files.
      exclude_docs: Optional boolean flag (default True) to exclude documentation and info pages.
      exclude_man: Optional boolean flag (default True) to exclude man pages.
      exclude_licenses: Optional boolean flag (default True) to exclude license files.
      exclude_build_id: Optional boolean flag (default True) to exclude .build-id debug links.
      exclude_patterns: Optional list of additional glob patterns to exclude from the layer.
      install_langs: Optional language locales to keep (e.g. 'en_US.UTF-8' or ['en_US.UTF-8']),
        filtering non-matching locale files and translation catalogs in /usr/share/locale and /usr/lib/locale.
      **kwargs: Extra common rule attributes (e.g. visibility, tags).
    """
    common_kwargs = propagate_common_rule_attributes(kwargs)
    intermediate_kwargs = dict(common_kwargs)
    intermediate_kwargs["visibility"] = ["//visibility:private"]

    patterns = list(exclude_patterns)
    if exclude_docs:
        patterns.extend(DOCS_PATTERNS)
    if exclude_man:
        patterns.extend(MAN_PATTERNS)
    if exclude_licenses:
        patterns.extend(LICENSES_PATTERNS)
    if exclude_build_id:
        patterns.extend(BUILD_ID_PATTERNS)

    install_langs_str = ""
    if install_langs:
        if type(install_langs) == "list":
            install_langs_str = ":".join(install_langs)
        else:
            install_langs_str = str(install_langs)

    raw_target = name + "_raw"
    rpm_merge(
        name = raw_target,
        rpms = rpms,
        rpmdb = rpmdb,
        gpgcheck = gpgcheck,
        gpgkeys = gpgkeys,
        exclude_patterns = patterns,
        out = name + "_raw.tar",
        **intermediate_kwargs
    )

    if not rpmdb and not compress:
        tar_dedup(
            name = name,
            src = ":" + raw_target,
            install_langs = install_langs_str,
            out = out or (name if name.endswith(".tar") else (name + ".tar")),
            **kwargs
        )
        return

    dedup_target = name + "_dedup"
    tar_dedup(
        name = dedup_target,
        src = ":" + raw_target,
        install_langs = install_langs_str,
        out = name + "_dedup.tar",
        **intermediate_kwargs
    )
    current_target = dedup_target

    if rpmdb:
        if not compress:
            rpmdb_inject(
                name = name,
                src = ":" + current_target,
                rpmdb = rpmdb,
                out = out or (name if name.endswith(".tar") else (name + ".tar")),
                **kwargs
            )
            return

        rpmdb_target = name + "_rpmdb"
        rpmdb_inject(
            name = rpmdb_target,
            src = ":" + current_target,
            rpmdb = rpmdb,
            out = name + "_rpmdb.tar",
            **intermediate_kwargs
        )
        current_target = rpmdb_target

    ext = ".tar.gz" if compress == "gzip" else ".tar.zst"
    final_out = out or (name if (name.endswith(".tar.gz") or name.endswith(".tar.zst")) else (name + ext))
    tar_compress(
        name = name,
        src = ":" + current_target,
        compress = compress,
        out = final_out,
        **kwargs
    )
