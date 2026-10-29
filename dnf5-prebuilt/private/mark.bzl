"""Implementation of the rpm_mark rule."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN", "dnf5_script", "render_dnf_config")

def _rpm_mark_impl(ctx):
    """Writes the rpmdb with `dnf5 rpmdb-mark` under a hermetic dnf_config."""
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
    script = ctx.actions.declare_file(ctx.label.name + "_mark.sh")
    ctx.actions.write(script, dnf5_script(dnf5.dnf5, info, "rpmdb-mark", lambda f: f.path), is_executable = True)

    args = ctx.actions.args()
    args.add("--rpmdb-root=" + out_dir.path)
    args.add("--archlist=" + ctx.attr.arch)
    if ctx.attr.nodeps:
        args.add("--nodeps")
    args.add_all(ctx.attr.packages)
    ctx.actions.run(
        inputs = info.files,
        outputs = [out_dir],
        executable = script,
        arguments = [args],
        tools = dnf5.files,
        # The install time of every package, so that the same packages give the same rpmdb.
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
    },
    doc = "Writes an rpmdb that records the packages and their dependencies, without installing them, with `dnf5 rpmdb-mark`.",
    toolchains = [DNF5_TOOLCHAIN],
)
