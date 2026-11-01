"""Implementation of rpm_lock rule."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN", "SOLVER_ATTRS", "render_dnf_config", "solver_settings")
load("//dnf5-prebuilt/private:providers.bzl", "DnfConfigInfo", "RpmLockFileInfo")

def _rpm_lock_impl(ctx):
    """Resolves RPM packages with rpm_lock tool and writes the lockfile."""
    out = ctx.outputs.out or ctx.actions.declare_file(ctx.label.name + ".lock.json")
    dnf5 = ctx.toolchains[DNF5_TOOLCHAIN].dnf5_info

    if ctx.attr.config:
        info = ctx.attr.config[DnfConfigInfo]
        arch = ctx.attr.arch if ctx.attr.arch else info.arch
        releasever = ctx.attr.releasever or info.releasever
        forcearch = ctx.attr.forcearch or info.forcearch
        module_enable = ctx.attr.module_enable or info.module_enable
    else:
        if not ctx.attr.releasever or not ctx.attr.repo_configs:
            fail("When 'config' is not specified, 'releasever' and 'repo_configs' must be provided.")
        info = render_dnf_config(
            ctx,
            ctx.label.name + "_dnf5",
            ctx.files.repo_configs,
            ctx.files.repo_files,
            ctx.attr.arch,
            **solver_settings(ctx.attr)
        )
        arch = ctx.attr.arch
        releasever = ctx.attr.releasever
        forcearch = ctx.attr.forcearch
        module_enable = ctx.attr.module_enable

    info_vars = dict(info.vars) if hasattr(info, "vars") and info.vars else {}
    all_vars = dict(info_vars)
    all_vars.update(ctx.attr.vars)

    args = ctx.actions.args()
    args.add("--output=" + out.path)
    args.add("--arch=" + ",".join(arch))
    if forcearch:
        args.add("--forcearch=" + forcearch)
    if releasever:
        args.add("--releasever=" + releasever)
    if ctx.attr.nobest:
        args.add("--nobest")
    if not ctx.attr.install_weak_deps:
        args.add("--no-weak-deps")
    for mod in module_enable:
        args.add("--module-enable=" + mod)
    if ctx.attr.module_platform_id:
        args.add("--module-platform-id=" + ctx.attr.module_platform_id)
    for exc in ctx.attr.exclude:
        args.add("--prune=" + exc)
    for k, v in all_vars.items():
        args.add("--setvar=%s=%s" % (k, v))
    if ctx.file.base_rpmdb:
        args.add("--base-rpmdb=" + ctx.file.base_rpmdb.path)
    if hasattr(info, "args_file") and info.args_file:
        args.add("--preamble-args=" + info.args_file.path)
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
        "--arch=" + ",".join(arch),
        "--config=" + info.conf.short_path,
        "--reposdir=" + repos_dir_short,
        "--repo-dir=" + info.repo_dir_short,
        "--dnf5=" + dnf5.dnf5.short_path,
        "--rpm=" + dnf5.rpm.short_path,
    ]
    if forcearch:
        run_args.append("--forcearch=" + forcearch)
    if releasever:
        run_args.append("--releasever=" + releasever)
    if ctx.attr.nobest:
        run_args.append("--nobest")
    if not ctx.attr.install_weak_deps:
        run_args.append("--no-weak-deps")
    for mod in module_enable:
        run_args.append("--module-enable=" + mod)
    if ctx.attr.module_platform_id:
        run_args.append("--module-platform-id=" + ctx.attr.module_platform_id)
    for exc in ctx.attr.exclude:
        run_args.append("--prune=" + exc)
    for k, v in all_vars.items():
        run_args.append("--setvar=%s=%s" % (k, v))
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

    runfiles_files = [out]
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
            arch = ",".join(arch),
            base_rpmdb = ctx.file.base_rpmdb,
            lock_file = out,
            packages = ctx.attr.packages,
        ),
    ]

_RPM_LOCK_ATTRS = dict(SOLVER_ATTRS)
_RPM_LOCK_ATTRS.update({
    "config": attr.label(
        providers = [DnfConfigInfo],
        doc = "Optional pre-rendered dnf_config target.",
    ),
    "arch": attr.string_list(
        default = ["x86_64", "noarch"],
        doc = "Target CPU architecture list (e.g. ['x86_64', 'noarch']).",
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
    "releasever": attr.string(
        doc = "Distribution release version (--releasever), e.g. '9'.",
    ),
    "repo_configs": attr.label_list(
        allow_files = [".repo", ".conf"],
        doc = "The .repo files defining repository configurations.",
    ),
    "repo_files": attr.label_list(
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
})

rpm_lock = rule(
    implementation = _rpm_lock_impl,
    doc = "Generates a hermetic RPM JSON lockfile for specified packages and dependencies, resolved with rpm_lock.",
    attrs = _RPM_LOCK_ATTRS,
    executable = True,
    toolchains = [DNF5_TOOLCHAIN],
)
