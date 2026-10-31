"""dnf5 toolchain: a prebuilt dnf5 distribution usable from Bazel actions."""

Dnf5Info = provider(
    doc = "A dnf5 distribution.",
    fields = {
        "dnf5": "File: bin/dnf5, the launcher to run in actions.",
        "rpm": "File: bin/rpm, the rpm launcher to run in actions (optional).",
        "files": "depset of File: every file of the distribution (inputs of actions running dnf5 or rpm).",
        "version": "string: dnf5 version.",
    },
)

def _dnf5_toolchain_impl(ctx):
    all_files = ctx.files.files + [ctx.file.dnf5]
    if ctx.file.rpm:
        all_files.append(ctx.file.rpm)
    files = depset(all_files)
    info = Dnf5Info(
        dnf5 = ctx.file.dnf5,
        rpm = ctx.file.rpm,
        files = files,
        version = ctx.attr.version,
    )
    return [
        platform_common.ToolchainInfo(dnf5_info = info),
        DefaultInfo(files = files),
    ]

dnf5_toolchain = rule(
    implementation = _dnf5_toolchain_impl,
    doc = "Defines a dnf5 toolchain from a dnf5 distribution (see the archives built by //bazel/release).",
    attrs = {
        "dnf5": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "The bin/dnf5 launcher of the distribution.",
        ),
        "rpm": attr.label(
            allow_single_file = True,
            doc = "The bin/rpm launcher of the distribution.",
        ),
        "files": attr.label_list(
            allow_files = True,
            doc = "All files of the distribution.",
        ),
        "version": attr.string(doc = "dnf5 version of the distribution."),
    },
)

def _current_dnf5_toolchain_impl(ctx):
    info = ctx.toolchains[Label("//dnf5-prebuilt:toolchain_type")].dnf5_info
    target_file = info.rpm if ctx.attr.binary == "rpm" else info.dnf5
    if not target_file:
        fail("Toolchain does not provide binary '%s'" % ctx.attr.binary)
    exe = ctx.actions.declare_file(ctx.label.name)
    ctx.actions.symlink(
        output = exe,
        target_file = target_file,
        is_executable = True,
    )
    make_vars = {"DNF5": exe.path} if ctx.attr.binary == "dnf5" else {"RPM": exe.path}
    return [
        info,
        DefaultInfo(
            executable = exe,
            files = depset([exe]),
            runfiles = ctx.runfiles(transitive_files = info.files).merge(ctx.runfiles([exe])),
        ),
        # $(DNF5) or $(RPM) in genrule cmd / run_binary args
        platform_common.TemplateVariableInfo(make_vars),
    ]

current_dnf5_toolchain = rule(
    implementation = _current_dnf5_toolchain_impl,
    doc = """Exposes a binary from the resolved dnf5 toolchain.

Provides Dnf5Info, the launcher plus the distribution as runfiles, and the
`$(DNF5)` or `$(RPM)` make variable, so it can be used in `toolchains` of a genrule or in
`srcs`/`tool` of other rules.""",
    executable = True,
    attrs = {
        "binary": attr.string(
            default = "dnf5",
            values = ["dnf5", "rpm"],
            doc = "Which binary launcher to expose ('dnf5' or 'rpm').",
        ),
    },
    toolchains = ["//dnf5-prebuilt:toolchain_type"],
)
