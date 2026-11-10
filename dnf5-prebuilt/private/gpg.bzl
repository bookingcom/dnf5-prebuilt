"""Shared GPG verification helper for dnf5-prebuilt rules."""

load("//dnf5-prebuilt/private:config.bzl", "DNF5_TOOLCHAIN")

def gpg_attrs():
    """Returns the common rule attribute dictionary for GPG signature validation."""
    return {
        "gpgcheck": attr.bool(
            default = False,
            doc = "Enable GPG signature validation of RPMs.",
        ),
        "gpgkeys": attr.label_list(
            allow_files = True,
            doc = "Optional list of GPG public key files.",
        ),
        "rpmdb": attr.label(
            allow_single_file = True,
            doc = "Optional rpmdb SQLite file containing GPG keys.",
        ),
        "_keystore_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_gpg_keystore"),
            executable = True,
            cfg = "exec",
        ),
        "_verify_tool": attr.label(
            default = Label("//dnf5-prebuilt/private:rpm_gpg_verify"),
            executable = True,
            cfg = "exec",
        ),
    }

def verify_rpms_gpg(ctx, rpms = None):
    """Performs GPG verification for a list of RPMs if gpgcheck or gpgkeys is specified.

    Args:
      ctx: Rule context.
      rpms: Optional list of File objects to verify. Defaults to ctx.files.rpms.

    Returns:
      A list of marker File objects representing successful verification.
    """
    should_verify = ctx.attr.gpgcheck or bool(ctx.files.gpgkeys)
    if not should_verify:
        return []

    dnf5_tc = ctx.toolchains[DNF5_TOOLCHAIN]
    if not dnf5_tc:
        fail("GPG validation in %s requires a registered dnf5 toolchain" % ctx.label)
    dnf5 = dnf5_tc.dnf5_info

    keystore_dir = ctx.actions.declare_directory(ctx.label.name + "_gpg_keystore")

    ks_args = ctx.actions.args()
    ks_args.add("--output", keystore_dir.path)
    ks_inputs = []
    if ctx.file.rpmdb:
        ks_args.add("--rpmdb", ctx.file.rpmdb.path)
        ks_inputs.append(ctx.file.rpmdb)
    if ctx.files.gpgkeys:
        for k in ctx.files.gpgkeys:
            ks_args.add("--key", k.path)
            ks_inputs.append(k)

    ctx.actions.run(
        mnemonic = "RpmGpgKeystore",
        progress_message = "Creating GPG keystore for %s" % ctx.label.name,
        executable = ctx.executable._keystore_tool,
        arguments = [ks_args],
        inputs = depset(ks_inputs),
        outputs = [keystore_dir],
        use_default_shell_env = True,
    )

    rpm_list = rpms if rpms != None else ctx.files.rpms
    keyring_type = "fs" if ctx.files.gpgkeys else "rpmdb"
    extra_inputs = []

    for rpm in rpm_list:
        verified_marker = ctx.actions.declare_file(ctx.label.name + "_" + rpm.basename + ".gpg_verified")
        v_args = ctx.actions.args()
        v_args.add("--rpm-bin", dnf5.rpm.path)
        v_args.add("--rpmdb", keystore_dir.path)
        v_args.add("--keyring", keyring_type)
        v_args.add("--rpm", rpm.path)
        v_args.add("--output", verified_marker.path)

        ctx.actions.run(
            mnemonic = "RpmGpgVerify",
            progress_message = "Verifying GPG signature for %s" % rpm.basename,
            executable = ctx.executable._verify_tool,
            arguments = [v_args],
            inputs = depset([rpm, keystore_dir], transitive = [dnf5.files]),
            outputs = [verified_marker],
            use_default_shell_env = True,
        )
        extra_inputs.append(verified_marker)

    return extra_inputs
