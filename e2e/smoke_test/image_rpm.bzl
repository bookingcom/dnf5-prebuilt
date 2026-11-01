"""Macros for extracting RPM environments from container images."""

load("@dnf5-prebuilt//dnf5-prebuilt:defs.bzl", "dnf_config")
load("@rules_containers_util//containers:defs.bzl", "image_extract")

def extract_image_rpm_environment(
        name,
        image,
        rpmdb_path,
        repo_files,
        releasever,
        vars = {},
        platform = "linux/amd64",
        **kwargs):
    """Extracts rpmdb and yum repository configuration from a container image.

    Args:
      name: prefix for generated target names.
      image: container image label to extract from.
      rpmdb_path: path to the rpmdb SQLite file inside the image.
      repo_files: list of .repo file paths inside the image.
      releasever: release version string.
      vars: dictionary of variable overrides.
      platform: container platform string.
      **kwargs: extra arguments forwarded to dnf_config.

    Creates targets:
      :<name>_rpmdb: Extracted rpmdb.sqlite file
      :<name>_<repo_basename>: Extracted repo config file(s)
      :<name>_dnf_config: dnf_config rule configured with the extracted repos
    """
    image_extract(
        name = name + "_rpmdb",
        file = rpmdb_path,
        image = image,
        out = name + "_rpmdb.sqlite",
        platform = platform,
    )

    repo_labels = []
    for rf in repo_files:
        base = rf.rsplit("/", 1)[-1]
        target_name = name + "_" + base.replace(".", "_")
        image_extract(
            name = target_name,
            file = rf,
            image = image,
            out = name + "_" + base,
            platform = platform,
        )
        repo_labels.append(":" + target_name)

    dnf_config(
        name = name + "_dnf_config",
        install_weak_deps = False,
        releasever = releasever,
        repo_configs = repo_labels,
        vars = vars,
        **kwargs
    )

def oraclelinux_9_environment(name = "ol9", image = "@oraclelinux_9_slim//:image", platform = "linux/amd64", **kwargs):
    extract_image_rpm_environment(
        name = name,
        image = image,
        platform = platform,
        releasever = "9",
        repo_files = ["/etc/yum.repos.d/oracle-linux-ol9.repo"],
        rpmdb_path = "/var/lib/rpm/rpmdb.sqlite",
        vars = {
            "ocidomain": "oracle.com",
            "ociregion": "",
        },
        **kwargs
    )

def oraclelinux_10_environment(name = "ol10", image = "@oraclelinux_10_slim//:image", platform = "linux/amd64", **kwargs):
    extract_image_rpm_environment(
        name = name,
        image = image,
        platform = platform,
        releasever = "10",
        repo_files = ["/etc/yum.repos.d/oracle-linux-ol10.repo"],
        rpmdb_path = "/usr/lib/sysimage/rpm/rpmdb.sqlite",
        vars = {
            "ocidomain": "oracle.com",
            "ociregion": "",
        },
        **kwargs
    )

def centos_stream_9_environment(name = "centos9", image = "@centos_stream_9//:image", platform = "linux/amd64", **kwargs):
    extract_image_rpm_environment(
        name = name,
        image = image,
        platform = platform,
        releasever = "9",
        repo_files = ["/etc/yum.repos.d/centos.repo"],
        rpmdb_path = "/var/lib/rpm/rpmdb.sqlite",
        vars = {
            "stream": "9-stream",
        },
        **kwargs
    )
