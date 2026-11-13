#!/usr/bin/env python3
"""Unit tests for rpm_script.py."""

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest


def _load_rpm_script_module():
    candidates = [
        os.path.join(os.path.dirname(__file__), "rpm_script.py"),
        os.path.join(os.path.dirname(__file__), "../../dnf5-prebuilt/private/rpm_script.py"),
    ]
    for c in candidates:
        if os.path.exists(c):
            spec = importlib.util.spec_from_file_location("rpm_script", c)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    # Runfiles search
    runfiles_dir = os.environ.get("RUNFILES_DIR")
    if runfiles_dir:
        for root, _, files in os.walk(runfiles_dir):
            if "rpm_script.py" in files:
                c = os.path.join(root, "rpm_script.py")
                spec = importlib.util.spec_from_file_location("rpm_script", c)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
    raise FileNotFoundError("Could not locate rpm_script.py")


_mod = _load_rpm_script_module()
extract_script = _mod.extract_script


class RpmScriptUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.mock_rpm = os.path.join(self.tmpdir.name, "mock_rpm.sh")
        # Create a mock rpm script that inspects arguments and responds accordingly
        with open(self.mock_rpm, "w") as f:
            f.write("""#!/bin/sh
for arg in "$@"; do
    if [ "$arg" = "[%{PREIN}]" ]; then
        if [ "$MOCK_HAS_PRE" = "1" ]; then
            printf "echo pre-install\\n"
        fi
        exit 0
    elif [ "$arg" = "[%{POSTIN}]" ]; then
        if [ "$MOCK_HAS_POST" = "1" ]; then
            printf "echo post-install\\n"
        fi
        exit 0
    fi
done
exit 0
""")
        os.chmod(self.mock_rpm, stat.S_IRWXU)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_extract_pre_script_present(self):
        os.environ["MOCK_HAS_PRE"] = "1"
        os.environ["MOCK_HAS_POST"] = "0"
        dummy_rpm = os.path.join(self.tmpdir.name, "pkg.rpm")
        with open(dummy_rpm, "wb") as f:
            f.write(b"rpm_dummy_data")

        content = extract_script(self.mock_rpm, dummy_rpm, "pre")
        self.assertEqual(content, b"echo pre-install\n")

    def test_extract_pre_script_absent(self):
        os.environ["MOCK_HAS_PRE"] = "0"
        os.environ["MOCK_HAS_POST"] = "1"
        dummy_rpm = os.path.join(self.tmpdir.name, "pkg.rpm")
        with open(dummy_rpm, "wb") as f:
            f.write(b"rpm_dummy_data")

        content = extract_script(self.mock_rpm, dummy_rpm, "pre")
        self.assertEqual(content, b"")

    def test_extract_post_script_present(self):
        os.environ["MOCK_HAS_PRE"] = "0"
        os.environ["MOCK_HAS_POST"] = "1"
        dummy_rpm = os.path.join(self.tmpdir.name, "pkg.rpm")
        with open(dummy_rpm, "wb") as f:
            f.write(b"rpm_dummy_data")

        content = extract_script(self.mock_rpm, dummy_rpm, "post")
        self.assertEqual(content, b"echo post-install\n")

    def test_extract_post_script_absent(self):
        os.environ["MOCK_HAS_PRE"] = "1"
        os.environ["MOCK_HAS_POST"] = "0"
        dummy_rpm = os.path.join(self.tmpdir.name, "pkg.rpm")
        with open(dummy_rpm, "wb") as f:
            f.write(b"rpm_dummy_data")

        content = extract_script(self.mock_rpm, dummy_rpm, "post")
        self.assertEqual(content, b"")

    def test_cli_execution(self):
        os.environ["MOCK_HAS_POST"] = "1"
        dummy_rpm = os.path.join(self.tmpdir.name, "pkg.rpm")
        with open(dummy_rpm, "wb") as f:
            f.write(b"rpm_dummy_data")
        out_file = os.path.join(self.tmpdir.name, "out.sh")

        subprocess.check_call([
            sys.executable,
            _mod.__file__,
            "--rpm-bin", self.mock_rpm,
            "--rpm", dummy_rpm,
            "--script", "post",
            "--output", out_file,
        ])

        with open(out_file, "rb") as f:
            out_content = f.read()
        self.assertEqual(out_content, b"echo post-install\n")


if __name__ == "__main__":
    unittest.main()
