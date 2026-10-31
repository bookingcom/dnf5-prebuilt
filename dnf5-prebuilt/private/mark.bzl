"""Implementation of the rpm_mark rule."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN", "render_dnf_config")

def _rpm_mark_impl(ctx):
    """Writes the rpmdb with rpm_mark under a hermetic dnf_config."""
    out_dir = ctx.actions.declare_directory(ctx.label.name)
    dnf5 = ctx.toolchains[DNF5_TOOLCHAIN].dnf5_info
    info = render_dnf_config(
        ctx,
        ctx.label.name + "_dnf5",
        [ctx.file.repo_config],
        ctx.files.repo_files,
        ctx.attr.arch.split(","),
        ctx.attr.releasever,
    )

    args = ctx.actions.args()
    args.add("--rpmdb-root=" + out_dir.path)
    args.add("--archlist=" + ctx.attr.arch)
    if ctx.attr.nodeps:
        args.add("--nodeps")
    if dnf5.rpm:
        args.add("--rpm=" + dnf5.rpm.path)
    args.add("--dnf5=" + dnf5.dnf5.path)
    args.add("--repo-dir=" + info.repo_dir)
    args.add("--config=" + info.conf.path)
    args.add("--reposdir=" + info.conf.dirname + "/repos.d")
    args.add_all(ctx.attr.packages)

    ctx.actions.run(
        inputs = depset(transitive = [info.files, dnf5.files]),
        outputs = [out_dir],
        executable = ctx.executable._mark_tool,
        arguments = [args],
        env = {"SOURCE_DATE_EPOCH": "0"},
        mnemonic = "RpmMark",
        progress_message = "Marking RPM packages into rpmdb %{output}",
    )
    return [DefaultInfo(files = depset([out_dir]))]

rpm_mark = rule(
    implementation = _rpm_mark_impl,
    attrs = {
        "packages": attr.string_list(
            mandatory = True,
            doc = "List of package specifications with optional versions (e.g. ['curl', 'libcurl=7.76.1']).",
        ),
        "repo_config": attr.label(
            mandatory = True,
            allow_single_file = True,
            doc = "Repository configuration file (.repo).",
        ),
        "repo_files": attr.label_list(
            allow_files = True,
            doc = "Repository files including RPMs and repodata metadata.",
        ),
        "releasever": attr.string(
            default = "9",
            doc = "Distribution release version.",
        ),
        "arch": attr.string(
            default = "x86_64,noarch",
            doc = "Comma-separated target architectures.",
        ),
        "nodeps": attr.bool(
            default = False,
            doc = "Whether to disable dependency resolution.",
        ),
        "_mark_tool": attr.label(
            default = Label("//dnf5-prebuilt/tools:rpm_mark"),
            executable = True,
            cfg = "exec",
        ),
    },
    doc = "Writes an rpmdb that records the packages and their dependencies, without installing them, with rpm_mark.",
    toolchains = [DNF5_TOOLCHAIN],
)
