#!/usr/bin/env python3
"""Unit tests for tar_dedup.py covering entry deduplication and locale filtering."""

import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest


def make_tar(path: str, members: list):
    """Creates a tar archive with given members: tuples of (name, type, content_or_linkname)."""
    with tarfile.open(path, "w:") as t:
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


class TarDedupUnitTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Find tar_dedup.py
        self.script_path = None
        runfiles_dir = os.environ.get("RUNFILES_DIR")
        if runfiles_dir:
            for root, dirs, files in os.walk(runfiles_dir):
                if "tar_dedup.py" in files:
                    self.script_path = os.path.join(root, "tar_dedup.py")
                    break

        if not self.script_path:
            candidates = [
                os.path.join(os.path.dirname(__file__), "tar_dedup.py"),
                os.path.join(os.path.dirname(__file__), "../../dnf5-prebuilt/private/tar_dedup.py"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    self.script_path = os.path.abspath(c)
                    break

        self.assertIsNotNone(self.script_path, "Could not locate tar_dedup.py")

        # Import functions directly for unit testing
        import importlib.util

        spec = importlib.util.spec_from_file_location("tar_dedup", self.script_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_install_langs(self):
        parse = self.module.parse_install_langs
        self.assertIsNone(parse(None))
        self.assertIsNone(parse(""))
        self.assertIsNone(parse("all"))
        self.assertIsNone(parse("ALL"))
        self.assertIsNone(parse("en_US:all"))

        langs = parse("en_US.UTF-8")
        self.assertIn("c", langs)
        self.assertIn("posix", langs)
        self.assertIn("en", langs)
        self.assertIn("en_us", langs)
        self.assertIn("en_us.utf-8", langs)
        self.assertNotIn("fr", langs)
        self.assertNotIn("de", langs)

        multi = parse("en_US:de_DE.UTF-8,fr")
        self.assertIn("en", multi)
        self.assertIn("de", multi)
        self.assertIn("fr", multi)
        self.assertNotIn("es", multi)

    def test_should_keep_locale(self):
        parse = self.module.parse_install_langs
        should_keep = self.module.should_keep_locale

        # When install_langs is None/all, keep everything
        self.assertTrue(should_keep("usr/share/locale/de/LC_MESSAGES/bash.mo", None))

        allowed = parse("en_US.UTF-8")
        # Regular files outside locale are always kept
        self.assertTrue(should_keep("usr/bin/bash", allowed))
        self.assertTrue(should_keep("usr/lib64/libc.so.6", allowed))
        self.assertTrue(should_keep("etc/pki/tls/cert.pem", allowed))

        # Root locale directories and alias files are always kept
        self.assertTrue(should_keep("usr/share/locale", allowed))
        self.assertTrue(should_keep("usr/share/locale/", allowed))
        self.assertTrue(should_keep("usr/share/locale/locale.alias", allowed))
        self.assertTrue(should_keep("usr/lib/locale", allowed))
        self.assertTrue(should_keep("usr/lib/locale/locale-archive", allowed))

        # C and POSIX base locales in usr/lib/locale are kept
        self.assertTrue(should_keep("usr/lib/locale/C.utf8/LC_CTYPE", allowed))

        # English translation catalogs are kept
        self.assertTrue(should_keep("usr/share/locale/en/LC_MESSAGES/bash.mo", allowed))
        self.assertTrue(should_keep("usr/share/locale/en_US/LC_MESSAGES/bash.mo", allowed))
        self.assertTrue(should_keep("usr/share/locale/en@boldquot/LC_MESSAGES/bash.mo", allowed))
        self.assertTrue(should_keep("usr/share/locale/en_GB/LC_MESSAGES/p11-kit.mo", allowed))

        # Foreign language catalogs and directories are dropped
        self.assertFalse(should_keep("usr/share/locale/de/LC_MESSAGES/bash.mo", allowed))
        self.assertFalse(should_keep("usr/share/locale/de", allowed))
        self.assertFalse(should_keep("usr/share/locale/fr/LC_MESSAGES/bash.mo", allowed))
        self.assertFalse(should_keep("usr/share/locale/fr", allowed))
        self.assertFalse(should_keep("usr/share/locale/zh_CN/LC_MESSAGES/coreutils.mo", allowed))
        self.assertFalse(should_keep("usr/lib/locale/fr_FR.utf8/LC_CTYPE", allowed))

    def test_cli_dedup_and_locale_filtering(self):
        in_tar = os.path.join(self.temp_dir.name, "input.tar")
        out_tar = os.path.join(self.temp_dir.name, "output.tar")

        members = [
            ("usr/bin", "dir", b""),
            ("usr/bin/curl", "file", b"old_curl_v1"),
            ("usr/share/locale", "dir", b""),
            ("usr/share/locale/locale.alias", "file", b"alias_content"),
            ("usr/share/locale/en", "dir", b""),
            ("usr/share/locale/en/LC_MESSAGES", "dir", b""),
            ("usr/share/locale/en/LC_MESSAGES/curl.mo", "file", b"curl_en_mo"),
            ("usr/share/locale/de", "dir", b""),
            ("usr/share/locale/de/LC_MESSAGES", "dir", b""),
            ("usr/share/locale/de/LC_MESSAGES/curl.mo", "file", b"curl_de_mo"),
            ("usr/share/locale/fr", "dir", b""),
            ("usr/share/locale/fr/LC_MESSAGES", "dir", b""),
            ("usr/share/locale/fr/LC_MESSAGES/curl.mo", "file", b"curl_fr_mo"),
            ("usr/bin/curl", "file", b"new_curl_v2"),  # Duplicate file: must overwrite
        ]
        make_tar(in_tar, members)

        # Run CLI with --install-langs=en_US.UTF-8
        cmd = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar,
            "--output",
            out_tar,
            "--install-langs",
            "en_US.UTF-8",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"tar_dedup failed: {res.stderr}")

        with tarfile.open(out_tar, "r:") as t:
            names = [m.name for m in t.getmembers()]

            # Verified deduplication: only 1 usr/bin/curl, first occurrence kept
            self.assertEqual(names.count("usr/bin/curl"), 1)
            curl_m = t.getmember("usr/bin/curl")
            with t.extractfile(curl_m) as f:
                self.assertEqual(f.read(), b"old_curl_v1")

            # Verified locale filtering
            self.assertIn("usr/share/locale", names)
            self.assertIn("usr/share/locale/locale.alias", names)
            self.assertIn("usr/share/locale/en", names)
            self.assertIn("usr/share/locale/en/LC_MESSAGES/curl.mo", names)

            # Excluded locales must not be present
            self.assertNotIn("usr/share/locale/de", names)
            self.assertNotIn("usr/share/locale/de/LC_MESSAGES", names)
            self.assertNotIn("usr/share/locale/de/LC_MESSAGES/curl.mo", names)
            self.assertNotIn("usr/share/locale/fr", names)
            self.assertNotIn("usr/share/locale/fr/LC_MESSAGES", names)
            self.assertNotIn("usr/share/locale/fr/LC_MESSAGES/curl.mo", names)

    def test_canonicalization_symlinked_parent(self):
        in_tar = os.path.join(self.temp_dir.name, "symlink_in.tar")
        out_tar = os.path.join(self.temp_dir.name, "symlink_out.tar")

        members = [
            ("usr/lib64", "dir", b""),
            ("lib64", "symlink", "usr/lib64"),
            ("lib64/libgcc_s-14-20251022.so.1", "file", b"libgcc_binary"),
            ("lib64/libgcc_s.so.1", "symlink", "libgcc_s-14-20251022.so.1"),
        ]
        make_tar(in_tar, members)

        cmd = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar,
            "--output",
            out_tar,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"tar_dedup failed: {res.stderr}")

        with tarfile.open(out_tar, "r:") as t:
            members_out = {m.name: m for m in t.getmembers()}
            # Top-level symlink lib64 -> usr/lib64 is preserved
            self.assertIn("lib64", members_out)
            self.assertTrue(members_out["lib64"].issym())
            self.assertEqual(members_out["lib64"].linkname, "usr/lib64")

            # Entries under lib64/ are rewritten to usr/lib64/
            self.assertNotIn("lib64/libgcc_s-14-20251022.so.1", members_out)
            self.assertNotIn("lib64/libgcc_s.so.1", members_out)
            self.assertIn("usr/lib64/libgcc_s-14-20251022.so.1", members_out)
            self.assertIn("usr/lib64/libgcc_s.so.1", members_out)

            # Symlink target remains unchanged
            self.assertEqual(members_out["usr/lib64/libgcc_s.so.1"].linkname, "libgcc_s-14-20251022.so.1")

    def test_canonicalization_nested_symlinked_parents(self):
        in_tar = os.path.join(self.temp_dir.name, "nested_in.tar")
        out_tar = os.path.join(self.temp_dir.name, "nested_out.tar")

        members = [
            ("a", "symlink", "b"),
            ("b/c", "symlink", "../d"),
            ("a/c/nested_file.txt", "file", b"nested_data"),
        ]
        make_tar(in_tar, members)

        cmd = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar,
            "--output",
            out_tar,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"tar_dedup failed: {res.stderr}")

        with tarfile.open(out_tar, "r:") as t:
            members_out = {m.name: m for m in t.getmembers()}
            self.assertIn("d/nested_file.txt", members_out)
            self.assertNotIn("a/c/nested_file.txt", members_out)
            self.assertNotIn("b/c/nested_file.txt", members_out)
            with t.extractfile(members_out["d/nested_file.txt"]) as f:
                self.assertEqual(f.read(), b"nested_data")

    def test_canonicalization_relative_link_sibling(self):
        in_tar = os.path.join(self.temp_dir.name, "sibling_in.tar")
        out_tar = os.path.join(self.temp_dir.name, "sibling_out.tar")

        members = [
            ("lib64", "symlink", "usr/lib64"),
            ("lib64/libfoo.so.1.0", "file", b"foo_content"),
            ("lib64/libfoo.so.1", "symlink", "libfoo.so.1.0"),
            ("lib64/libfoo.so", "symlink", "libfoo.so.1"),
        ]
        make_tar(in_tar, members)

        cmd = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar,
            "--output",
            out_tar,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"tar_dedup failed: {res.stderr}")

        with tarfile.open(out_tar, "r:") as t:
            members_out = {m.name: m for m in t.getmembers()}
            self.assertIn("usr/lib64/libfoo.so.1.0", members_out)
            self.assertIn("usr/lib64/libfoo.so.1", members_out)
            self.assertIn("usr/lib64/libfoo.so", members_out)
            self.assertEqual(members_out["usr/lib64/libfoo.so.1"].linkname, "libfoo.so.1.0")
            self.assertEqual(members_out["usr/lib64/libfoo.so"].linkname, "libfoo.so.1")

    def test_canonicalization_collision(self):
        in_tar = os.path.join(self.temp_dir.name, "collision_in.tar")
        out_tar = os.path.join(self.temp_dir.name, "collision_out.tar")

        members = [
            ("lib64", "symlink", "usr/lib64"),
            ("usr/lib64/duplicate.txt", "file", b"first_content"),
            ("lib64/duplicate.txt", "file", b"second_content"),
        ]
        make_tar(in_tar, members)

        cmd = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar,
            "--output",
            out_tar,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"tar_dedup failed: {res.stderr}")

        with tarfile.open(out_tar, "r:") as t:
            names = [m.name for m in t.getmembers()]
            self.assertEqual(names.count("usr/lib64/duplicate.txt"), 1)
            self.assertNotIn("lib64/duplicate.txt", names)

    def test_canonicalization_type_conflict(self):
        # 1. Directory followed by file at same canonical path
        in_tar1 = os.path.join(self.temp_dir.name, "conflict1_in.tar")
        out_tar1 = os.path.join(self.temp_dir.name, "conflict1_out.tar")
        members1 = [
            ("lib64", "symlink", "usr/lib64"),
            ("usr/lib64/conflict", "dir", b""),
            ("lib64/conflict", "file", b"file_content"),
        ]
        make_tar(in_tar1, members1)

        cmd1 = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar1,
            "--output",
            out_tar1,
        ]
        res1 = subprocess.run(cmd1, capture_output=True, text=True)
        self.assertNotEqual(res1.returncode, 0)
        self.assertIn("Type conflict", res1.stderr)

        # 2. File followed by directory at same canonical path
        in_tar2 = os.path.join(self.temp_dir.name, "conflict2_in.tar")
        out_tar2 = os.path.join(self.temp_dir.name, "conflict2_out.tar")
        members2 = [
            ("lib64", "symlink", "usr/lib64"),
            ("usr/lib64/conflict", "file", b"file_content"),
            ("lib64/conflict", "dir", b""),
        ]
        make_tar(in_tar2, members2)

        cmd2 = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar2,
            "--output",
            out_tar2,
        ]
        res2 = subprocess.run(cmd2, capture_output=True, text=True)
        self.assertNotEqual(res2.returncode, 0)
        self.assertIn("Type conflict", res2.stderr)

    def test_canonicalization_absolute_symlink_outside_layer(self):
        in_tar = os.path.join(self.temp_dir.name, "abs_symlink_in.tar")
        out_tar = os.path.join(self.temp_dir.name, "abs_symlink_out.tar")

        members = [
            ("etc/resolv.conf", "symlink", "/run/systemd/resolve/stub-resolv.conf"),
            ("dev/fd", "symlink", "/proc/self/fd"),
        ]
        make_tar(in_tar, members)

        cmd = [
            sys.executable,
            self.script_path,
            "--input",
            in_tar,
            "--output",
            out_tar,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"tar_dedup failed: {res.stderr}")

        with tarfile.open(out_tar, "r:") as t:
            members_out = {m.name: m for m in t.getmembers()}
            self.assertEqual(members_out["etc/resolv.conf"].linkname, "/run/systemd/resolve/stub-resolv.conf")
            self.assertEqual(members_out["dev/fd"].linkname, "/proc/self/fd")


if __name__ == "__main__":
    unittest.main()
