"""Implementation of rpm_lock rule."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN", "SOLVER_ATTRS", "dnf5_script", "render_dnf_config", "solver_settings")
load("//dnf5-prebuilt/private:providers.bzl", "DnfConfigInfo", "RpmLockFileInfo")

def _dnf5_lock_args(ctx, info, arch, forcearch, releasever, module_enable, all_vars, base_rpmdb, lock_files):
    """Arguments of `dnf5 lock` and any overrides not already in `info`."""
    args = ["--archlist=" + ",".join(arch)]
    if ctx.attr.config:
        if forcearch and forcearch != info.forcearch:
            args.append("--forcearch=" + forcearch)
        if releasever and releasever != info.releasever:
            args.append("--releasever=" + releasever)
        if ctx.attr.nobest:
            args.append("--no-best")
        if not ctx.attr.install_weak_deps:
            args.append("--setopt=install_weak_deps=False")
        if ctx.attr.module_platform_id:
            args.append("--setopt=module_platform_id=" + ctx.attr.module_platform_id)
        for exc in ctx.attr.excludepkgs:
            args.append("--exclude=" + exc)
        for k, v in all_vars.items():
            args.append("--setvar=%s=%s" % (k, v))

    args += ["--prune=" + pkg for pkg in ctx.attr.exclude]
    args += ["--module-enable=" + spec for spec in module_enable]
    if base_rpmdb:
        args.append("--base-rpmdb=" + base_rpmdb)
    args += ["--lockfile=" + lf for lf in lock_files]
    return args + ctx.attr.packages

def _rpm_lock_impl(ctx):
    """Solves with `dnf5 lock` under a hermetic dnf_config and writes the lockfile."""
    out = ctx.outputs.out or ctx.actions.declare_file(ctx.label.name + ".lock.json")
    dnf5 = ctx.toolchains[DNF5_TOOLCHAIN].dnf5_info

    if ctx.attr.config:
        info = ctx.attr.config[DnfConfigInfo]
        arch = ctx.attr.arch if ctx.attr.arch else info.arch
        releasever = ctx.attr.releasever or info.releasever
        forcearch = ctx.attr.forcearch or info.forcearch
        module_enable = ctx.attr.module_enable or info.module_enable
    else:
        repo_configs = list(ctx.files.repo_configs)
        if ctx.file.repo_config:
            repo_configs.append(ctx.file.repo_config)
        if not repo_configs:
            fail("When 'config' is not specified, 'repo_configs' (or 'repo_config') must be provided.")
        releasever = ctx.attr.releasever or "9"
        settings = solver_settings(ctx.attr)
        settings["releasever"] = releasever
        info = render_dnf_config(
            ctx,
            ctx.label.name + "_dnf5",
            repo_configs,
            ctx.files.repo_files,
            ctx.attr.arch,
            **settings
        )
        arch = ctx.attr.arch
        forcearch = ctx.attr.forcearch
        module_enable = ctx.attr.module_enable

    info_vars = dict(info.vars) if hasattr(info, "vars") and info.vars else {}
    all_vars = dict(info_vars)
    all_vars.update(ctx.attr.vars)

    build_script = ctx.actions.declare_file(ctx.label.name + "_build.sh")
    ctx.actions.write(build_script, dnf5_script(dnf5.dnf5, info, "lock", lambda f: f.path), is_executable = True)

    args = ctx.actions.args()
    args.add("--output=" + out.path)
    args.add_all(_dnf5_lock_args(
        ctx,
        info,
        arch,
        forcearch,
        releasever,
        module_enable,
        all_vars,
        ctx.file.base_rpmdb.path if ctx.file.base_rpmdb else None,
        [lf.path for lf in ctx.files.lock_files],
    ))

    inputs = list(ctx.files.lock_files)
    if ctx.file.base_rpmdb:
        inputs.append(ctx.file.base_rpmdb)

    ctx.actions.run(
        mnemonic = "RpmLock",
        progress_message = "Generating RPM lockfile %s" % out.short_path,
        executable = build_script,
        arguments = [args],
        inputs = depset(inputs, transitive = [info.files]),
        tools = dnf5.files,
        outputs = [out],
    )

    # 'bazel run' writes the lockfile into the source tree.
    out_dest = ctx.attr.out.name if ctx.attr.out else ctx.label.name + ".lock.json"
    runner_script = ctx.actions.declare_file(ctx.label.name + "_run.sh")
    solve = ctx.actions.declare_file(ctx.label.name + "_solve.sh")
    ctx.actions.write(solve, dnf5_script(dnf5.dnf5, info, "lock", lambda f: f.short_path), is_executable = True)

    run_args = _dnf5_lock_args(
        ctx,
        info,
        arch,
        forcearch,
        releasever,
        module_enable,
        all_vars,
        ctx.file.base_rpmdb.short_path if ctx.file.base_rpmdb else None,
        [lf.short_path for lf in ctx.files.lock_files],
    )
    dest_path = (ctx.label.package + "/" + out_dest) if ctx.label.package else out_dest

    ctx.actions.write(runner_script, """#!/usr/bin/env bash
set -euo pipefail

DEST="${BUILD_WORKSPACE_DIRECTORY}/%s"
TMP_OUT="$(mktemp)"
trap 'rm -f "${TMP_OUT}"' EXIT

"${PWD}/%s" --output="${TMP_OUT}" %s "$@"

mkdir -p "$(dirname "${DEST}")"
cp -f "${TMP_OUT}" "${DEST}"
echo "Lockfile updated at: ${DEST}"
""" % (
        dest_path,
        solve.short_path,
        " ".join(["'%s'" % a for a in run_args]),
    ), is_executable = True)

    runfiles_files = [out, solve] + list(ctx.files.lock_files)
    if ctx.file.base_rpmdb:
        runfiles_files.append(ctx.file.base_rpmdb)

    return [
        DefaultInfo(
            files = depset([out]),
            executable = runner_script,
            runfiles = ctx.runfiles(
                files = runfiles_files,
                transitive_files = depset(transitive = [info.files, dnf5.files]),
            ),
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
    "lock_files": attr.label_list(
        allow_files = [".json"],
        doc = "Ordered list of lock files from previous layers.",
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
    "repo_config": attr.label(
        allow_single_file = [".repo", ".conf"],
        doc = "Optional single .repo configuration file.",
    ),
    "repo_configs": attr.label_list(
        allow_files = [".repo", ".conf"],
        doc = "The .repo files defining repository configurations.",
    ),
    "repo_files": attr.label_list(
        allow_files = True,
        doc = "Repository metadata files (repodata XMLs, signatures) needed during dependency resolution.",
    ),
})

rpm_lock = rule(
    implementation = _rpm_lock_impl,
    doc = "Generates a hermetic RPM JSON lockfile for specified packages and dependencies, solved by `dnf5 lock`.",
    attrs = _RPM_LOCK_ATTRS,
    executable = True,
    toolchains = [DNF5_TOOLCHAIN],
)
