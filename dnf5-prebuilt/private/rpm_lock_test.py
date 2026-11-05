"""rpm_lock must fail, not silently drop scriptlet flags, when the RPMs to inspect cannot be downloaded.

dnf5 and rpm are replaced by shell stubs, so the test needs no network and no dnf5 toolchain:
  - `download --url --resolve` resolves the single package foo,
  - `repoquery` describes it,
  - `download --destdir=...` (the scriptlet download) behaves as FAKE_DOWNLOAD says: ok | fail | empty,
  - `rpm -qp` reports a %pre and no %post.
"""

import contextlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

_RPM_FILE = "foo-1.0-1.x86_64.rpm"

_FAKE_DNF5 = r"""#!/bin/sh
for a in "$@"; do
  case "$a" in
    repoquery)
      printf 'NAME:foo\nVERSION:1.0\nRELEASE:1\nEPOCH:0\nEVR:1.0-1\nARCH:x86_64\nNEVRA:foo-1.0-1.x86_64\n'
      printf 'LOCATION:Packages/%s\nREPOID:test\nREQUIRES:\nPROVIDES:\nfoo = 1.0-1\nRECOMMENDS:\n---RECORD_END---\n' "$RPM_FILE"
      exit 0;;
    --url)
      echo "https://example.invalid/Packages/$RPM_FILE"
      exit 0;;
    --destdir=*)
      case "$FAKE_DOWNLOAD" in
        fail) echo "simulated download failure" >&2; exit 1;;
        empty) exit 0;;
        *) : > "${a#--destdir=}/$RPM_FILE"; exit 0;;
      esac;;
  esac
done
exit 0
"""

_FAKE_RPM = """#!/bin/sh
printf 'echo pre---SEP---(none)'
"""


def _load_rpm_lock():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rpm_lock.py")
    spec = importlib.util.spec_from_file_location("rpm_lock", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_executable(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


class ScriptletDownloadTest(unittest.TestCase):
    def setUp(self):
        self.rpm_lock = _load_rpm_lock()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = self.tmp.name
        self.dnf5 = os.path.join(d, "dnf5")
        self.rpm = os.path.join(d, "rpm")
        _write_executable(self.dnf5, _FAKE_DNF5)
        _write_executable(self.rpm, _FAKE_RPM)
        self.output = os.path.join(d, "out", "foo.lock.json")

    def run_lock(self, fake_download):
        """Runs rpm_lock.main(); returns (exit code, stderr)."""
        argv = [
            "rpm_lock",
            "--dnf5=" + self.dnf5,
            "--rpm=" + self.rpm,
            "--config=" + os.path.join(self.tmp.name, "dnf.conf"),
            "--reposdir=" + os.path.join(self.tmp.name, "repos.d"),
            "--output=" + self.output,
            "foo",
        ]
        env = {"FAKE_DOWNLOAD": fake_download, "RPM_FILE": _RPM_FILE}
        stderr = io.StringIO()
        code = 0
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, env), contextlib.redirect_stderr(stderr):
            try:
                self.rpm_lock.main()
            except SystemExit as e:
                code = e.code
        return code, stderr.getvalue()

    def test_downloaded_rpm_is_inspected(self):
        # Control: proves the stubs reach scriptlet inspection, so the failures below are about the download.
        code, stderr = self.run_lock("ok")
        self.assertEqual(code, 0, stderr)
        with open(self.output, encoding="utf-8") as f:
            pkg = json.load(f)["packages"][0]
        self.assertEqual(pkg["name"], "foo")
        self.assertTrue(pkg["has_preinstall_script"])
        self.assertNotIn("has_postinstall_script", pkg)

    def test_failed_download_fails_the_lock(self):
        code, stderr = self.run_lock("fail")
        self.assertNotEqual(code, 0, "lock succeeded although the download failed")
        self.assertIn("simulated download failure", stderr)
        self.assertFalse(os.path.exists(self.output), "a lockfile without scriptlet flags was written")

    def test_rpm_missing_after_download_fails_the_lock(self):
        code, stderr = self.run_lock("empty")
        self.assertNotEqual(code, 0, "lock succeeded although the RPM never arrived")
        self.assertIn("foo", stderr)
        self.assertFalse(os.path.exists(self.output), "a lockfile without scriptlet flags was written")


if __name__ == "__main__":
    unittest.main()
