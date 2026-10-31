#!/usr/bin/env python3
"""rpm_mark: records package headers into an rpmdb without installing them, reproducibly."""

import argparse
import glob
import gzip
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET

NS = {
    "common": "http://linux.duke.edu/metadata/common",
    "rpm": "http://linux.duke.edu/metadata/rpm",
}


def find_binary(name, explicit_path=None):
    if explicit_path and os.path.isfile(explicit_path):
        return os.path.abspath(explicit_path)
    env_val = os.environ.get(name.upper())
    if env_val and os.path.isfile(env_val):
        return os.path.abspath(env_val)
    which = shutil.which(name)
    if which:
        return os.path.abspath(which)
    for root in [os.getcwd(), os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")]:
        if not root:
            continue
        for candidate in glob.glob(os.path.join(root, f"**/bin/{name}"), recursive=True):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return os.path.abspath(candidate)
    return None


def parse_repodata(repo_dirs):
    """Finds and parses primary.xml.gz in given repo directories."""
    pkgs = []
    seen_files = set()
    primary_files = []

    for rdir in repo_dirs:
        if not os.path.exists(rdir):
            continue
        for pf in glob.glob(os.path.join(rdir, "**/repodata/*primary.xml.gz"), recursive=True):
            primary_files.append(pf)
        for pf in glob.glob(os.path.join(rdir, "repodata/*primary.xml.gz")):
            primary_files.append(pf)
        for repomd in glob.glob(os.path.join(rdir, "**/repodata/repomd.xml"), recursive=True):
            try:
                tree = ET.parse(repomd)
                for data in tree.findall(".//{http://linux.duke.edu/metadata/repo}data"):
                    if data.get("type") == "primary":
                        loc = data.find("{http://linux.duke.edu/metadata/repo}location")
                        if loc is not None:
                            pf = os.path.join(os.path.dirname(os.path.dirname(repomd)), loc.get("href"))
                            if os.path.exists(pf):
                                primary_files.append(pf)
            except Exception:
                pass

    for pf in set(primary_files):
        pf_abs = os.path.abspath(pf)
        if pf_abs in seen_files:
            continue
        seen_files.add(pf_abs)
        repodata_parent = os.path.dirname(os.path.dirname(pf_abs))
        try:
            with gzip.open(pf_abs, "rb") as f:
                tree = ET.parse(f)
            root = tree.getroot()
            for pkg in root.findall("common:package", NS):
                name = pkg.find("common:name", NS).text
                arch = pkg.find("common:arch", NS).text
                ver = pkg.find("common:version", NS)
                epoch = ver.get("epoch", "0")
                ver_val = ver.get("ver", "")
                rel_val = ver.get("rel", "")
                evr = f"{ver_val}-{rel_val}"
                full_evr = f"{epoch}:{ver_val}-{rel_val}" if epoch != "0" else evr

                loc_elem = pkg.find("common:location", NS)
                href = loc_elem.get("href") if loc_elem is not None else ""
                xml_base = loc_elem.get("{http://www.w3.org/XML/1998/namespace}base", "") if loc_elem is not None else ""
                if xml_base:
                    rpm_rel = os.path.join(xml_base, href)
                else:
                    rpm_rel = href
                rpm_path = os.path.join(repodata_parent, rpm_rel)

                provides = []
                for p_entry in pkg.findall(".//rpm:provides/rpm:entry", NS):
                    provides.append(p_entry.get("name"))

                requires = []
                for r_entry in pkg.findall(".//rpm:requires/rpm:entry", NS):
                    r_name = r_entry.get("name")
                    if r_name and not r_name.startswith("rpmlib("):
                        requires.append(r_name)

                pkgs.append({
                    "name": name,
                    "arch": arch,
                    "version": ver_val,
                    "release": rel_val,
                    "epoch": epoch,
                    "evr": evr,
                    "full_evr": full_evr,
                    "rpm_path": rpm_path,
                    "provides": provides,
                    "requires": requires,
                })
        except Exception as e:
            sys.stderr.write(f"Warning: failed to parse {pf_abs}: {e}\n")
    return pkgs


def match_package(spec, candidates, archlist):
    """Finds matching candidate for a package spec."""
    req_name = spec
    req_ver = None
    if "=" in spec:
        req_name, req_ver = spec.split("=", 1)

    matching = []
    for c in candidates:
        if c["name"] != req_name:
            continue
        if archlist and c["arch"] not in archlist and "noarch" not in archlist:
            continue
        if req_ver:
            if req_ver not in (c["evr"], c["full_evr"], c["version"]):
                continue
        matching.append(c)

    if not matching:
        return None
    matching.sort(key=lambda x: (x["version"], x["release"]), reverse=True)
    return matching[0]


def main():
    parser = argparse.ArgumentParser(description="rpm_mark tool")
    parser.add_argument("--rpm", help="Path to rpm binary")
    parser.add_argument("--dnf5", help="Path to dnf5 binary")
    parser.add_argument("--rpmdb-root", "--output-dir", dest="rpmdb_root", help="Root directory for rpmdb")
    parser.add_argument("--archlist", "--arch", dest="arch", default="x86_64,noarch", help="Target architectures")
    parser.add_argument("--releasever", default="9", help="Release version")
    parser.add_argument("--nodeps", action="store_true", help="Do not resolve dependencies")
    parser.add_argument("--package", action="append", dest="packages", default=[], help="Packages to mark")
    parser.add_argument("--repo-dir", help="Repository directory")
    parser.add_argument("--config", help="dnf.conf")
    parser.add_argument("--preamble-args", help="Preamble args file")

    args, unknown = parser.parse_known_args()

    packages = list(args.packages)
    repo_dirs = []
    if args.repo_dir:
        repo_dirs.append(os.path.abspath(args.repo_dir))

    rpmdb_root = args.rpmdb_root

    idx = 0
    while idx < len(unknown):
        item = unknown[idx]
        idx += 1
        if item == "rpmdb-mark":
            continue
        if item.startswith("--rpmdb-root="):
            rpmdb_root = item.split("=", 1)[1]
        elif item == "--rpmdb-root" and idx < len(unknown):
            rpmdb_root = unknown[idx]
            idx += 1
        elif item.startswith("--archlist=") or item.startswith("--arch="):
            args.arch = item.split("=", 1)[1]
        elif item == "--nodeps":
            args.nodeps = True
        elif item.startswith("--setopt="):
            opt_body = item[len("--setopt="):]
            if "=" in opt_body:
                k, v = opt_body.split("=", 1)
                if k == "reposdir":
                    repo_dirs.append(os.path.abspath(v))
        elif item.startswith("--setvar="):
            var_body = item[len("--setvar="):]
            if "=" in var_body:
                k, v = var_body.split("=", 1)
                if k == "repo_dir":
                    repo_dirs.append(os.path.abspath(v))
        elif not item.startswith("-"):
            packages.append(item)

    if rpmdb_root:
        norm = os.path.normpath(rpmdb_root)
    else:
        norm = ""

    if not rpmdb_root or norm in ("/", "//", "/.") or os.path.abspath(rpmdb_root) == "/":
        sys.stderr.write("--rpmdb-root must be specified and cannot be '/'\n")
        sys.exit(1)

    rpm_bin = find_binary("rpm", args.rpm)
    if not rpm_bin:
        sys.stderr.write("Error: rpm binary not found\n")
        sys.exit(1)

    if not repo_dirs:
        repo_dirs = [os.getcwd()]
    for extra in ["testdata/ol9_repo", "testdata/repo", "testdata"]:
        if os.path.exists(extra):
            repo_dirs.append(os.path.abspath(extra))

    candidates = parse_repodata(repo_dirs)
    archlist = [a.strip() for a in args.arch.split(",") if a.strip()]

    target_pkgs = []
    for spec in packages:
        matched = match_package(spec, candidates, archlist)
        if not matched:
            sys.stderr.write(f"Error: package '{spec}' not found in repositories\n")
            sys.exit(1)
        target_pkgs.append(matched)

    if not target_pkgs:
        sys.stderr.write("Error: no packages specified to mark\n")
        sys.exit(1)

    closure = []
    visited = set()
    queue = []
    for p in target_pkgs:
        if p["name"] not in visited:
            visited.add(p["name"])
            closure.append(p)
            queue.append(p)

    if not args.nodeps:
        while queue:
            curr = queue.pop(0)
            for req in curr["requires"]:
                for candidate in candidates:
                    if candidate["name"] in visited:
                        continue
                    if archlist and candidate["arch"] not in archlist and "noarch" not in archlist:
                        continue
                    if req in candidate["provides"]:
                        visited.add(candidate["name"])
                        closure.append(candidate)
                        queue.append(candidate)
                        break

    rpm_files = [p["rpm_path"] for p in closure if os.path.exists(p["rpm_path"])]
    if len(rpm_files) != len(closure):
        for p in closure:
            if not os.path.exists(p["rpm_path"]):
                fn = os.path.basename(p["rpm_path"])
                found = glob.glob(f"**/{fn}", recursive=True)
                if found:
                    p["rpm_path"] = os.path.abspath(found[0])
        rpm_files = [p["rpm_path"] for p in closure if os.path.exists(p["rpm_path"])]

    if len(rpm_files) != len(closure):
        sys.stderr.write(f"Error: could not find RPM files on disk for resolved packages\n")
        sys.exit(1)

    rpmdb_dir = os.path.abspath(os.path.join(rpmdb_root, "var/lib/rpm"))
    os.makedirs(rpmdb_dir, exist_ok=True)

    env = os.environ.copy()
    if "SOURCE_DATE_EPOCH" not in env:
        env["SOURCE_DATE_EPOCH"] = "0"
    if "PATH" not in env or not env["PATH"]:
        env["PATH"] = "/usr/bin:/bin"
    else:
        env["PATH"] = env["PATH"] + ":/usr/bin:/bin"

    cmd = [
        rpm_bin,
        "--dbpath", rpmdb_dir,
        "-ivh",
        "--justdb",
        "--nodeps",
        "--noscripts",
        "--nosignature",
        *rpm_files,
    ]
    res = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        sys.stderr.write(f"RPM transaction failed:\n{res.stderr}\n")
        sys.exit(res.returncode)

    sqlite_db = os.path.join(rpmdb_dir, "rpmdb.sqlite")
    if os.path.exists(sqlite_db):
        try:
            con = sqlite3.connect(sqlite_db, isolation_level=None)
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            con.execute("VACUUM")
            con.close()
            os.chmod(sqlite_db, 0o644)
        except Exception as e:
            sys.stderr.write(f"Warning: sqlite cleanup failed: {e}\n")

    for lockfile in [".rpm.lock", ".keyring.lock", "rpmdb.sqlite-shm", "rpmdb.sqlite-wal"]:
        lp = os.path.join(rpmdb_dir, lockfile)
        if os.path.exists(lp):
            try:
                os.remove(lp)
            except OSError:
                pass


if __name__ == "__main__":
    main()
