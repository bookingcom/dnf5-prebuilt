"""Providers of the dnf5-prebuilt rules."""

RpmLockFileInfo = provider(
    doc = "Propagates generated RPM lockfile details and dependency closure.",
    fields = {
        "arch": "Target architecture(s) for the lockfile",
        "lock_file": "File object representing the output lock JSON file",
        "packages": "List of package names included in the lockfile",
    },
)

DnfConfigInfo = provider(
    doc = "A rendered dnf5 configuration and the command line preamble that pins it.",
    fields = {
        "arch": "Target architectures",
        "args_file": "File with the preamble, one argument per line, path tokens unexpanded",
        "conf": "The rendered dnf.conf; its directory is @CONFDIR@ in the preamble",
        "files": "Depset of everything the preamble refers to (dnf.conf, repos.d, repository files)",
        "forcearch": "Architecture passed as --forcearch, or empty",
        "module_enable": "Module streams (NAME:STREAM) the consuming action enables",
        "preamble": "List of dnf5 arguments with the tokens @CONFDIR@, @TMP@ and @REPODIR@ for the consumer to expand",
        "releasever": "Release version passed as --releasever",
        "repo_dir": "Execroot-relative directory of the local repository, the value of @REPODIR@",
        "repo_files": "List of the local repository files (repodata and packages)",
        "repos": "List of rendered .repo files",
    },
)
