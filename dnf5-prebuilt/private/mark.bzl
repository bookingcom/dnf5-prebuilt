"""Implementation of the rpm_mark rule."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN")

def _rpm_mark_impl(ctx):
    """Writes the rpmdb file with rpm_mark."""
    out = ctx.outputs.out or ctx.actions.declare_file(ctx.label.name + "/rpmdb.sqlite")
    dnf5 = ctx.toolchains[DNF5_TOOLCHAIN].dnf5_info

    args = ctx.actions.args()
    args.add("--output=" + out.path)
    if ctx.file.base_rpmdb:
        args.add("--base-rpmdb=" + ctx.file.base_rpmdb.path)
    args.add("--rpm=" + dnf5.rpm.path)
    args.add_all([f.path for f in ctx.files.rpms])

    inputs = list(ctx.files.rpms)
    if ctx.file.base_rpmdb:
        inputs.append(ctx.file.base_rpmdb)

    ctx.actions.run(
        inputs = depset(inputs, transitive = [dnf5.files]),
        outputs = [out],
        executable = ctx.executable._mark_tool,
        arguments = [args],
        mnemonic = "RpmMark",
        progress_message = "Marking RPM packages into rpmdb %{output}",
        use_default_shell_env = True,
    )
    return [DefaultInfo(files = depset([out]))]

rpm_mark = rule(
    implementation = _rpm_mark_impl,
    attrs = {
        "base_rpmdb": attr.label(
            allow_single_file = True,
            doc = "Optional base rpmdb file to mark packages on top of.",
        ),
        "out": attr.output(
            doc = "Optional output file. Defaults to <name>/rpmdb.sqlite.",
        ),
        "rpms": attr.label_list(
            mandatory = True,
            allow_files = [".rpm"],
            doc = "RPM package files to record in the rpmdb.",
        ),
        "_mark_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_mark"),
            executable = True,
            cfg = "exec",
        ),
    },
    doc = "Writes an rpmdb that records the RPM packages, without installing them, with rpm_mark.",
    toolchains = [DNF5_TOOLCHAIN],
)
