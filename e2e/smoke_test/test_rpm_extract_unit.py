#!/usr/bin/env python3
"""Unit tests for rpm_extract.py covering all symlink resolution and dereferencing cases."""

import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest


class MockBsdtar:
    """Creates a mock bsdtar executable that supports -tf and -xf using Python tarfile."""

    def __init__(self, directory: str):
        self.path = os.path.join(directory, "mock_bsdtar.py")
        with open(self.path, "w") as f:
            f.write("""#!/usr/bin/env python3
import sys, os, tarfile

args = sys.argv[1:]
if "-tf" in args:
    archive = args[args.index("-tf") + 1]
    with tarfile.open(archive, "r:*") as t:
        for m in t.getmembers():
            print(m.name)
elif "-xf" in args:
    archive = args[args.index("-xf") + 1]
    dest = "."
    if "-C" in args:
        dest = args[args.index("-C") + 1]
    files_to_extract = []
    i = 0
    while i < len(args):
        if args[i] in ("-xf", "-C"):
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            files_to_extract.append(args[i])
            i += 1
    with tarfile.open(archive, "r:*") as t:
        extract_kwargs = {"filter": lambda m, p: m} if hasattr(tarfile, "data_filter") else {}
        if files_to_extract:
            for name in files_to_extract:
                try:
                    m = t.getmember(name)
                    t.extract(m, dest, **extract_kwargs)
                except KeyError:
                    pass
        else:
            t.extractall(dest, **extract_kwargs)
""")
        os.chmod(self.path, 0o755)


def make_tar(path: str, members: list):
    """Creates a tar archive with given members: tuples of (name, type, content_or_linkname)."""
    with tarfile.open(path, "w") as t:
        for name, mtype, data in members:
            ti = tarfile.TarInfo(name)
            if mtype == "file":
                ti.size = len(data)
                ti.mode = 0o644
                t.addfile(ti, io.BytesIO(data))
            elif mtype == "symlink":
                ti.type = tarfile.SYMTYPE
                ti.linkname = data
                ti.mode = 0o777
                t.addfile(ti)
            elif mtype == "dir":
                ti.type = tarfile.DIRTYPE
                ti.mode = 0o755
                t.addfile(ti)


class RpmExtractTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_bsdtar = MockBsdtar(self.temp_dir.name).path
        # Find rpm_extract.py either via runfiles or relative path
        self.script_path = None
        runfiles_dir = os.environ.get("RUNFILES_DIR")
        if runfiles_dir:
            for root, dirs, files in os.walk(runfiles_dir):
                if "rpm_extract.py" in files:
                    self.script_path = os.path.join(root, "rpm_extract.py")
                    break

        if not self.script_path:
            candidates = [
                os.path.join(os.path.dirname(__file__), "rpm_extract.py"),
                os.path.join(os.path.dirname(__file__), "../../dnf5-prebuilt/private/rpm_extract.py"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    self.script_path = os.path.abspath(c)
                    break

        if not self.script_path:
            raise FileNotFoundError("Could not locate rpm_extract.py")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_extract(self, rpms, files=(), dirs=()):
        cmd = [sys.executable, self.script_path, "--bsdtar", self.mock_bsdtar]
        for rpm in rpms:
            cmd.extend(["--rpm", rpm])
        for src, dst in files:
            cmd.extend(["--file", src, dst])
        for src, dst in dirs:
            cmd.extend(["--dir", src, dst])
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_relative_symlink_dereference(self):
        pkg = os.path.join(self.temp_dir.name, "pkg.rpm")
        make_tar(pkg, [
            ("usr/lib64/libcurl.so.4.7.0", "file", b"curl-470"),
            ("usr/lib64/libcurl.so.4", "symlink", "libcurl.so.4.7.0"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_libcurl.so.4")
        res = self.run_extract([pkg], files=[("usr/lib64/libcurl.so.4", out_file)])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.exists(out_file))
        self.assertFalse(os.path.islink(out_file))
        with open(out_file, "rb") as f:
            self.assertEqual(f.read(), b"curl-470")

    def test_absolute_symlink_resolves_inside_tree(self):
        pkg = os.path.join(self.temp_dir.name, "pkg.rpm")
        make_tar(pkg, [
            ("usr/lib64/libcurl.so.4.7.0", "file", b"abs-curl-content"),
            ("usr/lib64/libcurl.so.4", "symlink", "/usr/lib64/libcurl.so.4.7.0"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_abs.so")
        res = self.run_extract([pkg], files=[("usr/lib64/libcurl.so.4", out_file)])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.exists(out_file))
        self.assertFalse(os.path.islink(out_file))
        with open(out_file, "rb") as f:
            self.assertEqual(f.read(), b"abs-curl-content")

    def test_climbing_symlink_clamped_at_root(self):
        pkg = os.path.join(self.temp_dir.name, "pkg.rpm")
        make_tar(pkg, [
            ("usr/lib64/libtarget.so", "file", b"clamped-target"),
            ("usr/lib64/climb.so", "symlink", "../../../../../usr/lib64/libtarget.so"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_climb.so")
        res = self.run_extract([pkg], files=[("usr/lib64/climb.so", out_file)])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.exists(out_file))
        self.assertFalse(os.path.islink(out_file))
        with open(out_file, "rb") as f:
            self.assertEqual(f.read(), b"clamped-target")

    def test_cross_rpm_symlink(self):
        pkg1 = os.path.join(self.temp_dir.name, "pkg1.rpm")
        pkg2 = os.path.join(self.temp_dir.name, "pkg2.rpm")
        make_tar(pkg1, [
            ("usr/lib64/libcurl.so.4", "symlink", "libcurl.so.4.7.0"),
        ])
        make_tar(pkg2, [
            ("usr/lib64/libcurl.so.4.7.0", "file", b"cross-rpm-content"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_cross.so")
        res = self.run_extract([pkg1, pkg2], files=[("usr/lib64/libcurl.so.4", out_file)])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.exists(out_file))
        self.assertFalse(os.path.islink(out_file))
        with open(out_file, "rb") as f:
            self.assertEqual(f.read(), b"cross-rpm-content")

    def test_install_order_overwrites(self):
        pkg1 = os.path.join(self.temp_dir.name, "pkg1.rpm")
        pkg2 = os.path.join(self.temp_dir.name, "pkg2.rpm")
        make_tar(pkg1, [
            ("usr/bin/tool", "file", b"version-1"),
        ])
        make_tar(pkg2, [
            ("usr/bin/tool", "file", b"version-2"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_tool")
        res = self.run_extract([pkg1, pkg2], files=[("usr/bin/tool", out_file)])
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(out_file, "rb") as f:
            self.assertEqual(f.read(), b"version-2")

    def test_missing_target_fails(self):
        pkg = os.path.join(self.temp_dir.name, "pkg.rpm")
        make_tar(pkg, [
            ("usr/lib64/broken.so", "symlink", "nonexistent.so"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_broken")
        res = self.run_extract([pkg], files=[("usr/lib64/broken.so", out_file)])
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Error: symlink target 'usr/lib64/nonexistent.so'", res.stderr)

    def test_missing_requested_entry_fails(self):
        pkg = os.path.join(self.temp_dir.name, "pkg.rpm")
        make_tar(pkg, [
            ("usr/bin/exists", "file", b"ok"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_missing")
        res = self.run_extract([pkg], files=[("usr/bin/not_here", out_file)])
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Error: requested entries were not found", res.stderr)

    def test_circular_symlink_fails(self):
        pkg = os.path.join(self.temp_dir.name, "pkg.rpm")
        make_tar(pkg, [
            ("usr/lib64/loop_a", "symlink", "loop_b"),
            ("usr/lib64/loop_b", "symlink", "loop_a"),
        ])
        out_file = os.path.join(self.temp_dir.name, "out_loop")
        res = self.run_extract([pkg], files=[("usr/lib64/loop_a", out_file)])
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("symlink cycle", res.stderr.lower())

    def test_directory_dereference(self):
        pkg = os.path.join(self.temp_dir.name, "pkg.rpm")
        make_tar(pkg, [
            ("etc/yum.repos.d", "dir", None),
            ("etc/yum.repos.d/local.repo", "file", b"repo-content"),
            ("usr/share/fedora.repo", "file", b"fedora-content"),
            ("etc/yum.repos.d/fedora.repo", "symlink", "/usr/share/fedora.repo"),
        ])
        out_dir = os.path.join(self.temp_dir.name, "out_repos_d")
        res = self.run_extract([pkg], dirs=[("etc/yum.repos.d", out_dir)])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.isdir(out_dir))

        local_repo = os.path.join(out_dir, "local.repo")
        self.assertTrue(os.path.exists(local_repo))
        self.assertFalse(os.path.islink(local_repo))
        with open(local_repo, "rb") as f:
            self.assertEqual(f.read(), b"repo-content")

        fedora_repo = os.path.join(out_dir, "fedora.repo")
        self.assertTrue(os.path.exists(fedora_repo))
        self.assertFalse(os.path.islink(fedora_repo))
        with open(fedora_repo, "rb") as f:
            self.assertEqual(f.read(), b"fedora-content")


if __name__ == "__main__":
    unittest.main()
