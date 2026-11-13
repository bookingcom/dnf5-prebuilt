"""Implementation of the rpm_script rule using run_binary."""

load("@bazel_lib//lib:run_binary.bzl", "run_binary")

def rpm_script(
        name,
        rpm,
        script = "",
        out = None,
        **kwargs):
    """Extracts pre or post installation scriptlets from an RPM package using rpm.

    Args:
        name: The target name and default output filename.
        rpm: The RPM package file (.rpm) to extract the script from.
        script: "pre" or "post". Defaults to "pre" if target name contains "pre", otherwise "post".
        out: Optional output file name. Defaults to name.
        **kwargs: Additional attributes passed to run_binary (e.g. visibility, tags).
    """
    output_file = out or name

    script_type = script
    if not script_type:
        target_name = name.lower()
        if "pre" in target_name:
            script_type = "pre"
        elif "post" in target_name:
            script_type = "post"
        else:
            fail("Attribute 'script' must be specified as 'pre' or 'post' for target %s" % name)

    rule_name = name if output_file != name else name + "_rule"

    run_binary(
        name = rule_name,
        tool = Label("//dnf5-prebuilt/private:rpm_script"),
        tools = [Label("//dnf5-prebuilt:current_rpm_toolchain")],
        srcs = [rpm],
        outs = [output_file],
        args = [
            "--rpm-bin",
            "$(location @dnf5-prebuilt//dnf5-prebuilt:current_rpm_toolchain)",
            "--rpm",
            "$(location %s)" % rpm,
            "--script",
            script_type,
            "--output",
            "$@",
        ],
        mnemonic = "RpmScript",
        progress_message = "Extracting %s-install script from %s" % (script_type, name),
        **kwargs
    )
