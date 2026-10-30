#!/usr/bin/env bash
# Prepares a release: stamps the integrity of the prebuilt archives in dist/
# into dnf5-prebuilt/private/versions.bzl, creates the source archive used by
# the Bazel Central Registry and prints the release notes.
#
# Usage: .github/workflows/release_prep.sh <tag> <dist dir>
#   <dist dir> must contain dnf5-<dnf5 version>-<platform>.tar.gz for every
#   platform of dnf5-prebuilt/private/platforms.bzl.
set -o errexit -o nounset -o pipefail

TAG=$1
DIST=$(realpath "$2")
VERSION=${TAG#v}
PREFIX="dnf5-prebuilt-${VERSION}"
ARCHIVE="dnf5-prebuilt-${TAG}.tar.gz"
DNF5_VERSION=$(sed -n 's/^DNF5_VERSION = "\(.*\)"/\1/p' bazel/extensions.bzl)
PLATFORMS=$(sed -n 's/^    "\([a-z0-9_]*\)": \[$/\1/p' dnf5-prebuilt/private/platforms.bzl)

integrity=""
for platform in $PLATFORMS; do
    file="$DIST/dnf5-${DNF5_VERSION}-${platform}.tar.gz"
    test -f "$file" || { echo "missing $file" >&2; exit 1; }
    sri="sha256-$(openssl dgst -sha256 -binary "$file" | base64)"
    integrity+="            \"${platform}\": \"${sri}\",\n"
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git archive --format=tar --prefix="${PREFIX}/" "${TAG}" | tar -x -C "$work"

# Stamp the module version and the integrity of the prebuilt archives.
sed -i.bak "0,/version = \"0.0.0\"/s//version = \"${VERSION}\"/" "$work/$PREFIX/MODULE.bazel"
python3 - "$work/$PREFIX/dnf5-prebuilt/private/versions.bzl" "$DNF5_VERSION" "$TAG" "$integrity" <<'PY'
import re, sys
path, dnf5_version, tag, integrity = sys.argv[1:]
src = open(path).read()
entry = '    "%s": {\n        "tag": "%s",\n        "integrity": {\n%s        },\n    },\n' % (
    dnf5_version, tag, integrity.replace("\\n", "\n"))
new, n = re.subn(r'    "%s": \{\n.*?\n    \},\n' % re.escape(dnf5_version), entry, src, flags=re.DOTALL)
if n != 1:
    sys.exit("could not find dnf5 %s in %s" % (dnf5_version, path))
open(path, "w").write(new)
PY
rm -f "$work/$PREFIX/MODULE.bazel.bak"
rm -f "$work/$PREFIX/REPO.bazel"
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime="@0" -C "$work" -cf - "$PREFIX" | gzip -n >"$ARCHIVE"

cat <<NOTES
Prebuilt [dnf5](https://github.com/rpm-software-management/dnf5) ${DNF5_VERSION}
for linux_amd64, linux_arm64, osx_amd64 and osx_arm64, built hermetically with
Bazel and usable as a Bazel toolchain.

## Using the Bazel module

\`\`\`starlark
bazel_dep(name = "dnf5-prebuilt", version = "${VERSION}")

dnf5 = use_extension("@dnf5-prebuilt//dnf5-prebuilt:extensions.bzl", "dnf5")
dnf5.toolchains()
use_repo(dnf5, "dnf5_toolchains")

register_toolchains("@dnf5_toolchains//:all")
\`\`\`

## Using the archives directly

Extract \`dnf5-${DNF5_VERSION}-<platform>.tar.gz\` anywhere and run \`dnf5/bin/dnf5\`.

| Archive | sha256 |
|---|---|
NOTES
for platform in $PLATFORMS; do
    file="dnf5-${DNF5_VERSION}-${platform}.tar.gz"
    echo "| ${file} | $(openssl dgst -sha256 -r "$DIST/$file" | cut -d' ' -f1) |"
done
cat <<NOTES

The archives bundle GPL/LGPL software (dnf5, rpm, librepo, ...); license texts
and the list of components are in \`share/licenses/\`. The corresponding
sources are the upstream releases referenced by this tag plus the patches in
this repository.
NOTES
