"""An rpm_lock case with its normalized lockfile, for the golden files in //testdata."""

load("@bazel_lib//lib:run_binary.bzl", "run_binary")
load("@dnf5-prebuilt//dnf5-prebuilt:defs.bzl", "rpm_lock")

def lock_golden(name, out, **kwargs):
    """Declares an rpm_lock <name> and <name>_norm.json, its lockfile with the sandbox paths replaced.

    //testdata:lock_golden diffs <name>_norm.json against the checked-in golden file of the case.

    Args:
      name: name of the rpm_lock target.
      out: lockfile name of the rpm_lock target.
      **kwargs: rpm_lock attributes; arch defaults to x86_64 and noarch, releasever to 9.
    """
    kwargs.setdefault("arch", ["x86_64", "noarch"])
    kwargs.setdefault("releasever", "9")
    rpm_lock(name = name, out = out, **kwargs)
    run_binary(
        name = name + "_norm",
        srcs = [out],
        outs = [name + "_norm.json"],
        args = ["$(location %s)" % out, "$(location %s_norm.json)" % name],
        tool = "//:normalize_lock",
    )
