"""Analysis tests of rpm_merge."""

load("@bazel_skylib//lib:unittest.bzl", "analysistest", "asserts")

def _distinct_gpg_markers_test_impl(ctx):
    env = analysistest.begin(ctx)
    verify = [a for a in analysistest.target_actions(env) if a.mnemonic == "RpmGpgVerify"]
    markers = [f.path for a in verify for f in a.outputs.to_list()]
    asserts.equals(env, 2, len(verify), "one RpmGpgVerify action per input RPM")
    asserts.equals(env, 2, len({m: None for m in markers}), "distinct marker paths: %s" % markers)
    return analysistest.end(env)

# Fails at analysis ("declared twice") if markers are named after the RPM basename only.
distinct_gpg_markers_test = analysistest.make(_distinct_gpg_markers_test_impl)
