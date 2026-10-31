"""Helpers for the rpm Bazel overlay."""

# Execroot-relative path of this repository, for private include dirs.
_ROOT = Label("//:BUILD.bazel").workspace_root

def private_includes(dirs):
    """Returns -iquote flags for rpm's private include directories.

    rpm's private headers use generic names (system.h, debug.h) that also exist
    in some dependencies' exported include paths (e.g. popt's src/), so they are
    passed with -iquote, which is searched first for "..." includes.

    Args:
      dirs: directories relative to the repository root, searched after the
        generated headers (bazel/) and misc/.

    Returns:
      A list of compiler flags.
    """
    flags = []
    for d in ["bazel", "misc"] + dirs:
        flags += ["-iquote", _ROOT + "/" + d if _ROOT else d]
    return flags
