"""Implementation of the rpm_extract rule and macro."""

load("@bazel_lib//lib:utils.bzl", "propagate_common_rule_attributes")
load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN")

TAR_TOOLCHAIN_TYPE = "@tar.bzl//tar/toolchain:type"

def _normalize_path(p):
    p = p.strip()
    for _ in range(len(p)):
        if p.startswith("./"):
            p = p[2:]
        elif p.startswith("/"):
            p = p[1:]
        else:
            break
    if p.endswith("/"):
        p = p[:-1]
    if not p or ".." in p.split("/"):
        fail("Invalid path '%s': must not be empty or contain '..'" % p)
    return p

def _rpm_extract_tree_impl(ctx):
    out = ctx.actions.declare_directory(ctx.label.name)
    tar_toolchain = ctx.toolchains[TAR_TOOLCHAIN_TYPE]
    bsdtar = tar_toolchain.tarinfo.binary

    extra_inputs = []
    if ctx.attr.gpgcheck or ctx.files.gpgkeys:
        dnf5_tc = ctx.toolchains[DNF5_TOOLCHAIN]
        if not dnf5_tc:
            fail("GPG validation in %s requires a registered dnf5 toolchain" % ctx.label)
        dnf5 = dnf5_tc.dnf5_info
        keystore_dir = ctx.actions.declare_directory(ctx.label.name + "_gpg_keystore")

        ks_args = ctx.actions.args()
        ks_args.add("--output", keystore_dir.path)
        ks_inputs = []
        if ctx.file.rpmdb:
            ks_args.add("--rpmdb", ctx.file.rpmdb.path)
            ks_inputs.append(ctx.file.rpmdb)
        if ctx.files.gpgkeys:
            for k in ctx.files.gpgkeys:
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

        keyring_type = "fs" if ctx.files.gpgkeys else "rpmdb"
        for rpm in ctx.files.rpms:
            verified_marker = ctx.actions.declare_file(ctx.label.name + "_" + rpm.basename + ".gpg_verified")
            v_args = ctx.actions.args()
            v_args.add("--rpm-bin", dnf5.rpm.path)
            v_args.add("--rpmdb", keystore_dir.path)
            v_args.add("--keyring", keyring_type)
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
    args.add("--bsdtar", bsdtar.path)
    args.add("--output-dir", out.path)
    for rpm in ctx.files.rpms:
        args.add("--rpm", rpm.path)
    for f in ctx.attr.files:
        args.add("--file", f)
    for d in ctx.attr.dirs:
        args.add("--dir", d)

    ctx.actions.run(
        mnemonic = "RpmExtractTree",
        progress_message = "Extracting entries from RPMs into %s" % out.short_path,
        executable = ctx.executable._extract_tool,
        arguments = [args],
        inputs = depset(ctx.files.rpms + extra_inputs, transitive = [tar_toolchain.default.files]),
        outputs = [out],
        env = tar_toolchain.tarinfo.default_env,
    )
    return [DefaultInfo(files = depset([out]))]

rpm_extract_tree = rule(
    doc = "Extracts requested files and directories from RPMs into an intermediate directory.",
    implementation = _rpm_extract_tree_impl,
    attrs = {
        "dirs": attr.string_list(doc = "List of directory paths to extract."),
        "files": attr.string_list(doc = "List of file paths to extract."),
        "gpgcheck": attr.bool(
            default = False,
            doc = "Enable GPG signature validation of RPMs.",
        ),
        "gpgkeys": attr.label_list(
            allow_files = True,
            doc = "Optional list of GPG public key files.",
        ),
        "rpmdb": attr.label(
            allow_single_file = True,
            doc = "Optional rpmdb SQLite file containing GPG keys.",
        ),
        "rpms": attr.label_list(
            allow_files = [".rpm"],
            mandatory = True,
            doc = "RPM package files to extract from.",
        ),
        "_extract_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_extract"),
            executable = True,
            cfg = "exec",
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
    toolchains = [
        TAR_TOOLCHAIN_TYPE,
        config_common.toolchain_type(str(DNF5_TOOLCHAIN), mandatory = False),
    ],
)

def _rpm_extract_entry_impl(ctx):
    if ctx.attr.is_dir:
        out = ctx.actions.declare_directory(ctx.label.name)
    else:
        out = ctx.actions.declare_file(ctx.label.name)

    args = ctx.actions.args()
    args.add("--src", ctx.file.tree.path + "/" + ctx.attr.path)
    args.add("--dst", out.path)
    if ctx.attr.is_dir:
        args.add("--is-dir")

    ctx.actions.run(
        mnemonic = "RpmExtractEntry",
        progress_message = "Exposing extracted %s" % ctx.label.name,
        executable = ctx.executable._tool,
        arguments = [args],
        inputs = [ctx.file.tree],
        outputs = [out],
    )
    return [DefaultInfo(files = depset([out]), runfiles = ctx.runfiles(files = [out]))]

rpm_extract_entry = rule(
    doc = "Exposes a single extracted file or directory from an extracted tree.",
    implementation = _rpm_extract_entry_impl,
    attrs = {
        "is_dir": attr.bool(default = False, doc = "Whether the entry is a directory."),
        "path": attr.string(mandatory = True, doc = "Relative path of entry in tree."),
        "tree": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "Extracted tree directory.",
        ),
        "_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_extract_entry"),
            executable = True,
            cfg = "exec",
        ),
    },
)

def rpm_extract(
        name,
        rpms,
        files = [],
        dirs = [],
        directories = [],
        gpgcheck = False,
        gpgkeys = [],
        rpmdb = None,
        **kwargs):
    """Extracts requested files and directories from RPM packages and makes them available as targets.

    The target names match the fully-qualified relative paths passed in `files` and `dirs`,
    and are not shortened to basenames.

    Args:
      name: Target name for the aggregate filegroup.
      rpms: List of RPM package files (.rpm).
      files: List of file paths to extract from the RPMs (e.g. ['usr/bin/curl']).
      dirs: List of directory paths to extract from the RPMs (e.g. ['etc/pki/tls']).
      directories: Alias for dirs.
      gpgcheck: Optional boolean flag to enable GPG signature validation of RPMs.
      gpgkeys: Optional list of GPG public key files. Automatically enables gpgcheck.
      rpmdb: Optional rpmdb SQLite database file containing trusted GPG keys.
      **kwargs: Extra common rule attributes (e.g. visibility, tags).
    """
    raw_dirs = list(dirs) + list(directories)
    norm_files = []
    seen_files = {}
    for f in files:
        nf = _normalize_path(f)
        if nf not in seen_files:
            seen_files[nf] = True
            norm_files.append(nf)

    norm_dirs = []
    seen_dirs = {}
    for d in raw_dirs:
        nd = _normalize_path(d)
        if nd not in seen_dirs:
            seen_dirs[nd] = True
            norm_dirs.append(nd)

    if not norm_files and not norm_dirs:
        fail("rpm_extract target '%s' must specify at least one file or directory to extract in 'files' or 'dirs'" % name)

    for nf in norm_files:
        if nf in seen_dirs:
            fail("Path '%s' in rpm_extract target '%s' cannot be specified in both files and dirs" % (nf, name))

    common_kwargs = propagate_common_rule_attributes(kwargs)
    intermediate_kwargs = dict(common_kwargs)
    intermediate_kwargs["visibility"] = ["//visibility:private"]

    tree_name = "_" + name + "_tree"
    rpm_extract_tree(
        name = tree_name,
        rpms = rpms,
        files = norm_files,
        dirs = norm_dirs,
        gpgcheck = gpgcheck or bool(gpgkeys),
        gpgkeys = gpgkeys,
        rpmdb = rpmdb,
        **intermediate_kwargs
    )

    all_targets = []
    for f in norm_files:
        rpm_extract_entry(
            name = f,
            tree = ":" + tree_name,
            path = f,
            is_dir = False,
            **kwargs
        )
        all_targets.append(":" + f)

    for d in norm_dirs:
        rpm_extract_entry(
            name = d,
            tree = ":" + tree_name,
            path = d,
            is_dir = True,
            **kwargs
        )
        all_targets.append(":" + d)

    if name not in seen_files and name not in seen_dirs:
        native.filegroup(
            name = name,
            srcs = all_targets,
            **kwargs
        )
