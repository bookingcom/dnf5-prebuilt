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
        [ctx.file.repo_config],
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
    for lf in ctx.files.lock_files:
        args.add("--lockfile=" + lf.path)
    args.add("--config=" + info.conf.path)
    args.add("--reposdir=" + info.conf.dirname + "/repos.d")
    args.add("--repo-dir=" + info.repo_dir)
    args.add("--dnf5=" + dnf5.dnf5.path)
    if dnf5.rpm:
        args.add("--rpm=" + dnf5.rpm.path)
    args.add_all(ctx.attr.packages)

    ctx.actions.run(
        mnemonic = "RpmLock",
        progress_message = "Generating RPM lockfile %s" % out.short_path,
        executable = ctx.executable._lock_tool,
        arguments = [args],
        inputs = depset(ctx.files.lock_files, transitive = [info.files, dnf5.files]),
        outputs = [out],
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
    for lf in ctx.files.lock_files:
        run_args.append("--lockfile=" + lf.short_path)
    run_args.extend(ctx.attr.packages)

    tool_rel = ctx.executable._lock_tool.short_path
    if tool_rel.startswith("../"):
        tool_rel = tool_rel[3:]

    ctx.actions.write(runner_script, """#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${RUNFILES_DIR:-}" ]]; then
  if [[ -d "${0}.runfiles" ]]; then
    export RUNFILES_DIR="${0}.runfiles"
  fi
fi

TOOL=""
if [[ -n "${RUNFILES_DIR:-}" ]]; then
  for cand in \
    "${RUNFILES_DIR}/%s" \
    "${RUNFILES_DIR}/_main/%s" \
    "${RUNFILES_DIR}/dnf5-prebuilt/%s" \
    "${PWD}/%s"; do
    if [[ -x "${cand}" ]]; then
      TOOL="${cand}"
      break
    fi
  done
  if [[ -z "${TOOL}" ]]; then
    TOOL="$(find "${RUNFILES_DIR}" -type f -name rpm_lock 2>/dev/null | head -n 1)"
  fi
fi

if [[ -z "${TOOL}" && -x "${PWD}/%s" ]]; then
  TOOL="${PWD}/%s"
fi

if [[ -z "${TOOL}" ]]; then
  echo "Error: rpm_lock tool executable not found" >&2
  exit 1
fi

DEST="${BUILD_WORKSPACE_DIRECTORY}/%s/%s"
TMP_OUT="$(mktemp)"
trap 'rm -f "${TMP_OUT}"' EXIT

"${TOOL}" --output="${TMP_OUT}" %s "$@"

mkdir -p "$(dirname "${DEST}")"
cp -f "${TMP_OUT}" "${DEST}"
echo "Lockfile updated at: ${DEST}"
""" % (
        tool_rel,
        tool_rel,
        tool_rel,
        ctx.executable._lock_tool.short_path,
        ctx.executable._lock_tool.short_path,
        ctx.executable._lock_tool.short_path,
        ctx.label.package,
        out_dest,
        " ".join(["'%s'" % a for a in run_args]),
    ), is_executable = True)

    runfiles = ctx.runfiles(
        files = ctx.files.lock_files,
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
        ),
    ]

rpm_lock = rule(
    implementation = _rpm_lock_impl,
    doc = "Generates a hermetic RPM JSON lockfile for specified packages and dependencies, resolved with rpm_lock.",
    attrs = SOLVER_ATTRS | {
        "repo_config": attr.label(
            mandatory = True,
            allow_single_file = [".repo"],
            doc = "The .repo file defining repository configurations.",
        ),
        "repo_files": attr.label_list(
            mandatory = True,
            allow_files = True,
            doc = "Repository files (repodata, RPMs) needed during dependency resolution.",
        ),
        "arch": attr.string_list(
            mandatory = True,
            allow_empty = False,
            doc = "Mandatory target CPU architecture list (e.g. ['x86_64', 'noarch']).",
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
        "_lock_tool": attr.label(
            default = Label("//dnf5-prebuilt/tools:rpm_lock"),
            executable = True,
            cfg = "exec",
        ),
    },
    executable = True,
    toolchains = [DNF5_TOOLCHAIN],
)
