"""Implementation of the multi-pass rpm_layer rule and macro."""

load("@bazel_lib//lib:utils.bzl", "propagate_common_rule_attributes")
load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN")

TAR_TOOLCHAIN_TYPE = "@tar.bzl//tar/toolchain:type"

def _rpm_merge_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out or (ctx.label.name + ".tar"))
    tar_toolchain = ctx.toolchains[TAR_TOOLCHAIN_TYPE]
    bsdtar = tar_toolchain.tarinfo.binary

    extra_inputs = []
    if ctx.attr.gpgcheck:
        keystore_dir = ctx.actions.declare_directory(ctx.label.name + "_gpg_keystore")
        dnf5 = ctx.toolchains[DNF5_TOOLCHAIN].dnf5_info

        ks_args = ctx.actions.args()
        ks_args.add("--output", keystore_dir.path)
        ks_inputs = []
        if ctx.file.rpmdb:
            ks_args.add("--rpmdb", ctx.file.rpmdb.path)
            ks_inputs.append(ctx.file.rpmdb)
        if ctx.files.gpg_keys:
            for k in ctx.files.gpg_keys:
                ks_args.add("--key", k.path)
                ks_inputs.append(k)

        ctx.actions.run(
            mnemonic = "RpmGpgKeystore",
            progress_message = "Creating GPG keystore for %s" % ctx.label.name,
            executable = ctx.executable._keystore_tool,
            arguments = [ks_args],
            inputs = depset(ks_inputs),
            outputs = [keystore_dir],
            use_default_shell_env = True,
        )

        for rpm in ctx.files.rpms:
            verified_marker = ctx.actions.declare_file(ctx.label.name + "_" + rpm.basename + ".gpg_verified")
            v_args = ctx.actions.args()
            v_args.add("--rpm-bin", dnf5.rpm.path)
            v_args.add("--keystore", keystore_dir.path)
            v_args.add("--rpm", rpm.path)
            v_args.add("--output", verified_marker.path)

            ctx.actions.run(
                mnemonic = "RpmGpgVerify",
                progress_message = "Verifying GPG signature for %s" % rpm.basename,
                executable = ctx.executable._verify_tool,
                arguments = [v_args],
                inputs = depset([rpm, keystore_dir], transitive = [dnf5.files]),
                outputs = [verified_marker],
                use_default_shell_env = True,
            )
            extra_inputs.append(verified_marker)

    args = ctx.actions.args()
    args.add("-cf", out)
    args.add("--format=pax")
    args.add("--numeric-owner")
    args.add("--owner=0")
    args.add("--group=0")
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
    attrs = {
        "gpg_keys": attr.label_list(
            allow_files = True,
            doc = "Optional list of GPG public key files.",
        ),
        "gpgcheck": attr.bool(
            default = False,
            doc = "Enable GPG signature validation of RPMs.",
        ),
        "out": attr.string(doc = "Optional output file name. Defaults to <name>.tar."),
        "rpmdb": attr.label(
            allow_single_file = True,
            doc = "Optional rpmdb SQLite file containing GPG keys.",
        ),
        "rpms": attr.label_list(
            allow_files = [".rpm"],
            mandatory = True,
            doc = "RPM package files to extract and merge.",
        ),
        "_keystore_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_gpg_keystore"),
            executable = True,
            cfg = "exec",
        ),
        "_verify_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_gpg_verify"),
            executable = True,
            cfg = "exec",
        ),
    },
    toolchains = [TAR_TOOLCHAIN_TYPE, DNF5_TOOLCHAIN],
)

def _tar_dedup_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out or (ctx.label.name + ".tar"))
    args = ctx.actions.args()
    args.add("--input", ctx.file.src)
    args.add("--output", out)

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
    doc = "Deduplicates tar directory entries and files, keeping the last occurrence.",
    implementation = _tar_dedup_impl,
    attrs = {
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
        gpg_keys = [],
        **kwargs):
    """Assembles RPM packages into an OCI container layer tarball.

    Implements a multi-pass approach:
    1. If gpgcheck is enabled, creates a GPG keystore and verifies each RPM's signature against it.
    2. Merge all RPMs with bsdtar into an uncompressed archive (depends on verification).
    3. Iterate over the entries and deduplicate directory and file paths with Python.
    4. Inject rpmdb into the archive (if rpmdb is specified).
    5. Compress the layer (if compress='gzip' or 'zstd' is specified).

    Args:
      name: Target name.
      rpms: List of RPM package files.
      rpmdb: Optional updated rpmdb SQLite file.
      compress: Optional compression algorithm ('gzip' or 'zstd').
      out: Optional explicit output file name.
      gpgcheck: Optional boolean flag to enable GPG signature validation of RPMs.
      gpg_check: Optional alias for gpgcheck.
      gpg_keys: Optional list of GPG public key files.
      **kwargs: Extra common rule attributes (e.g. visibility, tags).
    """
    check = gpg_check if gpg_check != None else gpgcheck
    common_kwargs = propagate_common_rule_attributes(kwargs)
    intermediate_kwargs = dict(common_kwargs)
    intermediate_kwargs["visibility"] = ["//visibility:private"]

    raw_target = name + "_raw"
    rpm_merge(
        name = raw_target,
        rpms = rpms,
        rpmdb = rpmdb,
        gpgcheck = check,
        gpg_keys = gpg_keys,
        out = name + "_raw.tar",
        **intermediate_kwargs
    )

    if not rpmdb and not compress:
        tar_dedup(
            name = name,
            src = ":" + raw_target,
            out = out or (name if name.endswith(".tar") else (name + ".tar")),
            **kwargs
        )
        return

    dedup_target = name + "_dedup"
    tar_dedup(
        name = dedup_target,
        src = ":" + raw_target,
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
