"""Implementation of the rpm_extract rule and macro."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN")
load("//dnf5-prebuilt/private:gpg.bzl", "gpg_attrs", "verify_rpms_gpg")

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

def _rpm_extract_impl(ctx):
    tar_toolchain = ctx.toolchains[TAR_TOOLCHAIN_TYPE]
    bsdtar = tar_toolchain.tarinfo.binary

    gpg_inputs = verify_rpms_gpg(ctx)

    declared_files = []
    output_groups = {}
    for f in ctx.attr.files:
        out_f = ctx.actions.declare_file(ctx.label.name + "/" + f)
        declared_files.append(out_f)
        output_groups[f] = depset([out_f])

    declared_dirs = []
    for d in ctx.attr.dirs:
        out_d = ctx.actions.declare_directory(ctx.label.name + "/" + d)
        declared_dirs.append(out_d)
        output_groups[d] = depset([out_d])

    all_outputs = declared_files + declared_dirs

    args = ctx.actions.args()
    args.add("--bsdtar", bsdtar.path)
    for rpm in ctx.files.rpms:
        args.add("--rpm", rpm.path)
    for f, out_f in zip(ctx.attr.files, declared_files):
        args.add("--file")
        args.add(f)
        args.add(out_f.path)
    for d, out_d in zip(ctx.attr.dirs, declared_dirs):
        args.add("--dir")
        args.add(d)
        args.add(out_d.path)

    ctx.actions.run(
        mnemonic = "RpmExtract",
        progress_message = "Extracting entries from RPMs for %s" % ctx.label.name,
        executable = ctx.executable._extract_tool,
        arguments = [args],
        inputs = depset(ctx.files.rpms + gpg_inputs, transitive = [tar_toolchain.default.files]),
        outputs = all_outputs,
        env = tar_toolchain.tarinfo.default_env,
    )

    all_depset = depset(all_outputs)
    return [
        DefaultInfo(files = all_depset, runfiles = ctx.runfiles(files = all_outputs)),
        OutputGroupInfo(**output_groups),
    ]

_rpm_extract_attrs = {
    "dirs": attr.string_list(doc = "List of directory paths to extract."),
    "files": attr.string_list(doc = "List of file paths to extract."),
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
}
_rpm_extract_attrs.update(gpg_attrs())

_rpm_extract = rule(
    doc = "Extracts requested files and directories from RPMs in a single action, dereferencing all symlinks.",
    implementation = _rpm_extract_impl,
    attrs = _rpm_extract_attrs,
    toolchains = [
        TAR_TOOLCHAIN_TYPE,
        config_common.toolchain_type(str(DNF5_TOOLCHAIN), mandatory = False),
    ],
)

def rpm_extract(
        name,
        rpms,
        files = [],
        dirs = [],
        gpgcheck = False,
        gpgkeys = [],
        rpmdb = None,
        **kwargs):
    """Extracts requested files and directories from RPM packages and makes them available as targets.

    The target names are prefixed with `name + "/" + path` (e.g. `:my_extract/usr/bin/curl`).
    The top-level target `:name` provides all extracted files and directories.
    If any extracted entry is or contains a symlink in the RPM, it is automatically
    dereferenced into regular files and directories.

    Args:
      name: Target name for the aggregate extraction rule.
      rpms: List of RPM package files (.rpm).
      files: List of file paths to extract from the RPMs (e.g. ['usr/bin/curl']).
      dirs: List of directory paths to extract from the RPMs (e.g. ['etc/pki/tls']).
      gpgcheck: Optional boolean flag to enable GPG signature validation of RPMs.
      gpgkeys: Optional list of GPG public key files. Automatically enables gpgcheck.
      rpmdb: Optional rpmdb SQLite database file containing trusted GPG keys.
      **kwargs: Extra common rule attributes (e.g. visibility, tags).
    """
    norm_files = []
    seen_files = {}
    for f in files:
        nf = _normalize_path(f)
        if nf not in seen_files:
            seen_files[nf] = True
            norm_files.append(nf)

    norm_dirs = []
    seen_dirs = {}
    for d in dirs:
        nd = _normalize_path(d)
        if nd not in seen_dirs:
            seen_dirs[nd] = True
            norm_dirs.append(nd)

    if not norm_files and not norm_dirs:
        fail("rpm_extract target '%s' must specify at least one file or directory to extract in 'files' or 'dirs'" % name)

    for nf in norm_files:
        if nf in seen_dirs:
            fail("Path '%s' in rpm_extract target '%s' cannot be specified in both files and dirs" % (nf, name))

    if name in seen_files or name in seen_dirs:
        fail("rpm_extract target name '%s' cannot be identical to an extracted path in files or dirs" % name)

    _rpm_extract(
        name = name,
        rpms = rpms,
        files = norm_files,
        dirs = norm_dirs,
        gpgcheck = gpgcheck,
        gpgkeys = gpgkeys,
        rpmdb = rpmdb,
        **kwargs
    )

    for f in norm_files:
        native.filegroup(
            name = name + "/" + f,
            srcs = [":" + name],
            output_group = f,
            **kwargs
        )

    for d in norm_dirs:
        native.filegroup(
            name = name + "/" + d,
            srcs = [":" + name],
            output_group = d,
            **kwargs
        )
