"""Implementation of rpm_lock rule."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN", "SOLVER_ATTRS", "render_dnf_config", "solver_settings")
load("//dnf5-prebuilt/private:providers.bzl", "RpmLockFileInfo")

def _rpm_lock_impl(ctx):
    """Resolves RPM packages with rpm_lock tool and writes the lockfile."""
    out = ctx.outputs.out or ctx.actions.declare_file(ctx.label.name + ".lock.json")
    dnf5 = ctx.toolchains[DNF5_TOOLCHAIN].dnf5_info
    info = render_dnf_config(
        ctx,
        ctx.label.name + "_dnf5",
        ctx.files.repo_configs,
        ctx.files.repo_files,
        ctx.attr.arch,
        **solver_settings(ctx.attr)
    )

    args = ctx.actions.args()
    args.add("--output=" + out.path)
    args.add("--arch=" + ",".join(ctx.attr.arch))
    if ctx.attr.forcearch:
        args.add("--forcearch=" + ctx.attr.forcearch)
    if ctx.attr.releasever:
        args.add("--releasever=" + ctx.attr.releasever)
    if ctx.attr.nobest:
        args.add("--nobest")
    if not ctx.attr.install_weak_deps:
        args.add("--no-weak-deps")
    for mod in ctx.attr.module_enable:
        args.add("--module-enable=" + mod)
    if ctx.attr.module_platform_id:
        args.add("--module-platform-id=" + ctx.attr.module_platform_id)
    for exc in ctx.attr.exclude:
        args.add("--prune=" + exc)
    if ctx.file.base_rpmdb:
        args.add("--base-rpmdb=" + ctx.file.base_rpmdb.path)
    args.add("--config=" + info.conf.path)
    args.add("--reposdir=" + info.conf.dirname + "/repos.d")
    args.add("--repo-dir=" + info.repo_dir)
    args.add("--dnf5=" + dnf5.dnf5.path)
    args.add("--rpm=" + dnf5.rpm.path)
    args.add_all(ctx.attr.packages)

    inputs = []
    if ctx.file.base_rpmdb:
        inputs.append(ctx.file.base_rpmdb)

    ctx.actions.run(
        mnemonic = "RpmLock",
        progress_message = "Generating RPM lockfile %s" % out.short_path,
        executable = ctx.executable._lock_tool,
        arguments = [args],
        inputs = depset(inputs, transitive = [info.files, dnf5.files]),
        outputs = [out],
        use_default_shell_env = True,
    )

    # 'bazel run' writes the lockfile into the source tree.
    out_dest = ctx.attr.out.name if ctx.attr.out else ctx.label.name + ".lock.json"
    runner_script = ctx.actions.declare_file(ctx.label.name + "_run.sh")

    conf_dir_short = info.conf.short_path.rsplit("/", 1)[0] if "/" in info.conf.short_path else ""
    repos_dir_short = conf_dir_short + "/repos.d" if conf_dir_short else "repos.d"

    run_args = [
        "--arch=" + ",".join(ctx.attr.arch),
        "--config=" + info.conf.short_path,
        "--reposdir=" + repos_dir_short,
        "--repo-dir=" + info.repo_dir_short,
        "--dnf5=" + dnf5.dnf5.short_path,
        "--rpm=" + dnf5.rpm.short_path,
    ]
    if ctx.attr.forcearch:
        run_args.append("--forcearch=" + ctx.attr.forcearch)
    if ctx.attr.releasever:
        run_args.append("--releasever=" + ctx.attr.releasever)
    if ctx.attr.nobest:
        run_args.append("--nobest")
    if not ctx.attr.install_weak_deps:
        run_args.append("--no-weak-deps")
    for mod in ctx.attr.module_enable:
        run_args.append("--module-enable=" + mod)
    if ctx.attr.module_platform_id:
        run_args.append("--module-platform-id=" + ctx.attr.module_platform_id)
    for exc in ctx.attr.exclude:
        run_args.append("--prune=" + exc)
    if ctx.file.base_rpmdb:
        run_args.append("--base-rpmdb=" + ctx.file.base_rpmdb.short_path)
    run_args.extend(ctx.attr.packages)

    tool_rel = ctx.executable._lock_tool.short_path
    if tool_rel.startswith("../"):
        tool_rlocation = tool_rel[3:]
    else:
        tool_rlocation = (ctx.workspace_name or "_main") + "/" + tool_rel

    dest_path = (ctx.label.package + "/" + out_dest) if ctx.label.package else out_dest

    ctx.actions.expand_template(
        template = ctx.file._runner_template,
        output = runner_script,
        substitutions = {
            "%{DEST_PATH}": dest_path,
            "%{RUN_ARGS}": " ".join(["'%s'" % a for a in run_args]),
            "%{TOOL_RLOCATION}": tool_rlocation,
        },
        is_executable = True,
    )

    runfiles_files = []
    if ctx.file.base_rpmdb:
        runfiles_files.append(ctx.file.base_rpmdb)

    runfiles = ctx.runfiles(
        files = runfiles_files,
        transitive_files = depset(transitive = [info.files, dnf5.files]),
    ).merge(ctx.attr._lock_tool[DefaultInfo].default_runfiles)

    return [
        DefaultInfo(
            files = depset([out]),
            executable = runner_script,
            runfiles = runfiles,
        ),
        RpmLockFileInfo(
            lock_file = out,
            arch = ",".join(ctx.attr.arch),
            packages = ctx.attr.packages,
            base_rpmdb = ctx.file.base_rpmdb,
        ),
    ]

rpm_lock = rule(
    implementation = _rpm_lock_impl,
    doc = "Generates a hermetic RPM JSON lockfile for specified packages and dependencies, resolved with rpm_lock.",
    attrs = SOLVER_ATTRS | {
        "arch": attr.string_list(
            mandatory = True,
            allow_empty = False,
            doc = "Mandatory target CPU architecture list (e.g. ['x86_64', 'noarch']).",
        ),
        "base_rpmdb": attr.label(
            allow_single_file = True,
            doc = "Optional base rpmdb file containing already installed packages.",
        ),
        "exclude": attr.string_list(
            doc = "Optional packages to exclude and prune from the dependency tree.",
        ),
        "out": attr.output(
            doc = "Output JSON lockfile name.",
        ),
        "packages": attr.string_list(
            mandatory = True,
            allow_empty = False,
            doc = "List of RPM packages to lock (names, name-version, or provides).",
        ),
        "repo_configs": attr.label_list(
            mandatory = True,
            allow_files = [".repo"],
            doc = "The .repo files defining repository configurations.",
        ),
        "repo_files": attr.label_list(
            mandatory = True,
            allow_files = True,
            doc = "Repository metadata files (repodata XMLs, signatures) needed during dependency resolution.",
        ),
        "_lock_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_lock"),
            executable = True,
            cfg = "exec",
        ),
        "_runner_template": attr.label(
            default = Label("//dnf5-prebuilt/private:lock_runner.sh.tpl"),
            allow_single_file = True,
        ),
    },
    executable = True,
    toolchains = [DNF5_TOOLCHAIN],
)
