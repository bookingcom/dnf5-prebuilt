#!/usr/bin/env python3
"""rpm_lock: generates a hermetic RPM lockfile using dnf5 and repomd."""

import argparse
import base64
import configparser
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

import repomd


def parse_args():
    parser = argparse.ArgumentParser(description="rpm_lock tool")
    parser.add_argument("--dnf5", required=True, help="Path to dnf5 launcher")
    parser.add_argument("--rpm", required=True, help="Path to rpm launcher")
    parser.add_argument("--config", required=True, help="Path to dnf.conf")
    parser.add_argument("--preamble-args", help="Path to preamble args file")
    parser.add_argument("-o", "--output", dest="output", required=True, help="Output lockfile path")
    parser.add_argument("--archlist", "--arch", dest="arch", default="x86_64,noarch", help="Target architectures")
    parser.add_argument("--forcearch", help="Force solver architecture")
    parser.add_argument("--releasever", default="9", help="Release version")
    parser.add_argument("--nobest", action="store_true", help="Allow older package candidates")
    parser.add_argument("--no-weak-deps", action="store_true", help="Disable weak dependencies")
    parser.add_argument("--module-enable", action="append", default=[], help="Module streams to enable")
    parser.add_argument("--module-platform-id", help="Platform module ID")
    parser.add_argument("--prune", action="append", default=[], help="Packages to prune")
    parser.add_argument("--exclude", "--excludepkgs", action="append", dest="excludepkgs", default=[], help="NEVRA globs to exclude")
    parser.add_argument("--setvar", action="append", default=[], help="Variable definitions NAME=VALUE")
    parser.add_argument("--base-rpmdb", help="Path to base rpmdb.sqlite")
    parser.add_argument("--reposdir", required=True, help="Path to repos.d")
    parser.add_argument("--repo-dir", help="Path to repo directory")
    parser.add_argument("packages", nargs="+", help="Requested packages")
    return parser.parse_args()


def load_checksums_from_repomd(repos_dir, repo_dir_var):
    """Loads package checksums using repomd across all repository configs."""
    checksum_map = {}
    if not os.path.isdir(repos_dir):
        return checksum_map

    for repo_file in sorted(os.listdir(repos_dir)):
        if not repo_file.endswith(".repo"):
            continue
        repo_path = os.path.join(repos_dir, repo_file)
        cp = configparser.ConfigParser(interpolation=None)
        try:
            cp.read(repo_path, encoding="utf-8")
        except Exception:
            continue

        for section in cp.sections():
            baseurl = cp.get(section, "baseurl", fallback=None)
            if not baseurl:
                continue
            if repo_dir_var:
                baseurl = baseurl.replace("@REPO_DIR@", repo_dir_var).replace("${repo_dir}", repo_dir_var)
            try:
                repo = repomd.load(baseurl)
                for pkg in repo:
                    if pkg.checksum:
                        checksum_map[pkg.location] = (pkg.checksum, pkg.name)
                        checksum_map[os.path.basename(pkg.location)] = (pkg.checksum, pkg.name)
            except Exception as e:
                sys.stderr.write(f"Warning: repomd failed to load repo {baseurl}: {e}\n")

    return checksum_map


def parse_repoquery_output(output):
    """Parses dnf5 repoquery --queryformat records."""
    packages = []
    records = output.split("---RECORD_END---")
    for rec in records:
        rec = rec.strip()
        if not rec:
            continue
        pkg_data = {
            "name": "",
            "version": "",
            "release": "",
            "epoch": "0",
            "evr": "",
            "arch": "",
            "nevra": "",
            "location": "",
            "repoid": "",
            "requires": [],
            "provides": [],
            "recommends": [],
        }
        current_field = None
        for line in rec.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            if line_s.startswith("NAME:"):
                pkg_data["name"] = line_s[5:].strip()
                current_field = None
            elif line_s.startswith("VERSION:"):
                pkg_data["version"] = line_s[8:].strip()
                current_field = None
            elif line_s.startswith("RELEASE:"):
                pkg_data["release"] = line_s[8:].strip()
                current_field = None
            elif line_s.startswith("EPOCH:"):
                pkg_data["epoch"] = line_s[6:].strip()
                current_field = None
            elif line_s.startswith("EVR:"):
                pkg_data["evr"] = line_s[4:].strip()
                current_field = None
            elif line_s.startswith("ARCH:"):
                pkg_data["arch"] = line_s[5:].strip()
                current_field = None
            elif line_s.startswith("NEVRA:"):
                pkg_data["nevra"] = line_s[6:].strip()
                current_field = None
            elif line_s.startswith("LOCATION:"):
                pkg_data["location"] = line_s[9:].strip()
                current_field = None
            elif line_s.startswith("REPOID:"):
                pkg_data["repoid"] = line_s[7:].strip()
                current_field = None
            elif line_s.startswith("REQUIRES:"):
                current_field = "requires"
            elif line_s.startswith("PROVIDES:"):
                current_field = "provides"
            elif line_s.startswith("RECOMMENDS:"):
                current_field = "recommends"
            elif current_field:
                pkg_data[current_field].append(line_s)

        if pkg_data["name"]:
            packages.append(pkg_data)

    return packages


def capability_matches(req, provides_list):
    """Checks if a requirement capability is satisfied by a package provides list."""
    req_name = req.split()[0]
    for prov in provides_list:
        prov_name = prov.split()[0]
        if req == prov or req_name == prov_name:
            return True
    return False


def main():
    args = parse_args()

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = os.path.join(tmp_dir, "root")
        rpm_dir = os.path.join(root, "var", "lib", "rpm")
        sys_rpm_dir = os.path.join(root, "usr", "lib", "sysimage", "rpm")
        os.makedirs(rpm_dir, exist_ok=True)
        os.makedirs(sys_rpm_dir, exist_ok=True)

        if args.base_rpmdb and os.path.exists(args.base_rpmdb):
            target_rpmdb = os.path.join(rpm_dir, "rpmdb.sqlite")
            target_sys_rpmdb = os.path.join(sys_rpm_dir, "rpmdb.sqlite")
            shutil.copyfile(args.base_rpmdb, target_rpmdb)
            shutil.copyfile(args.base_rpmdb, target_sys_rpmdb)
            os.chmod(target_rpmdb, 0o644)
            os.chmod(target_sys_rpmdb, 0o644)

        conf_dir = os.path.dirname(os.path.abspath(args.config))
        repo_dir_abs = os.path.abspath(args.repo_dir) if args.repo_dir else ""

        dnf5_base = [os.path.abspath(args.dnf5)]
        if args.preamble_args and os.path.exists(args.preamble_args):
            with open(args.preamble_args, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    line = line.replace("@CONFDIR@", conf_dir)
                    line = line.replace("@REPODIR@", repo_dir_abs)
                    line = line.replace("@TMP@", tmp_dir)
                    dnf5_base.append(line)
        else:
            dnf5_base.extend([
                f"--config={os.path.abspath(args.config)}",
                f"--installroot={root}",
                f"--setopt=reposdir={os.path.abspath(args.reposdir)}",
                f"--setopt=cachedir={os.path.join(tmp_dir, 'cache')}",
                f"--setopt=logdir={os.path.join(tmp_dir, 'log')}",
                f"--setopt=persistdir={os.path.join(tmp_dir, 'persist')}",
                f"--setopt=system_state_dir={os.path.join(tmp_dir, 'state')}",
                f"--setopt=transaction_history_dir={os.path.join(tmp_dir, 'history')}",
                f"--setopt=debugdir={os.path.join(tmp_dir, 'debug')}",
                "--setopt=varsdir=",
                f"--setopt=pluginconfpath={os.path.join(tmp_dir, 'plugins.d')}",
                f"--setopt=plugin_conf_dir={os.path.join(tmp_dir, 'plugins.d')}",
                f"--setopt=pluginpath={os.path.join(tmp_dir, 'plugins')}",
                f"--releasever={args.releasever}",
            ])
            if repo_dir_abs:
                dnf5_base.append(f"--setvar=repo_dir={repo_dir_abs}")
            for sv in args.setvar:
                dnf5_base.append(f"--setvar={sv}")
            if args.forcearch:
                dnf5_base.append(f"--forcearch={args.forcearch}")
            else:
                first_arch = next((a for a in args.arch.split(",") if a != "noarch"), "")
                if first_arch:
                    dnf5_base.append(f"--forcearch={first_arch}")

        if args.nobest:
            dnf5_base.append("--no-best")
        if args.no_weak_deps:
            dnf5_base.append("--setopt=install_weak_deps=False")
        for exc in args.excludepkgs + args.prune:
            dnf5_base.append(f"--exclude={exc}")

        # Enable requested modules
        for mod in args.module_enable:
            subprocess.run(dnf5_base + ["module", "enable", "-y", mod], check=True, capture_output=True)

        # Resolve packages via dnf5 download --url --resolve
        dl_cmd = list(dnf5_base) + ["download", "--url", "--resolve"]
        for a in args.arch.split(","):
            a = a.strip()
            if a:
                dl_cmd.append(f"--arch={a}")
        if not args.base_rpmdb:
            dl_cmd.append("--alldeps")
        dl_cmd.extend(args.packages)

        res = subprocess.run(dl_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            sys.stderr.write(f"dnf5 resolution failed:\n{res.stderr}\n")
            sys.exit(res.returncode)

        resolved_urls = [
            l.strip()
            for l in res.stdout.splitlines()
            if l.strip() and not l.startswith("Updating") and not l.startswith("Repositories loaded")
        ]

        # Target specific packages in repoquery to avoid querying entire repo
        query_targets = list(args.packages)
        for u in resolved_urls:
            base = os.path.basename(u)
            if base.endswith(".rpm"):
                base = base[:-4]
            if "." in base:
                base = base.rsplit(".", 1)[0]
            if "-" in base:
                parts = base.split("-")
                if len(parts) >= 3:
                    pname = "-".join(parts[:-2])
                    if pname not in query_targets:
                        query_targets.append(pname)
        if not query_targets:
            query_targets = ["*"]

        # Query metadata for all resolved packages
        q_cmd = list(dnf5_base) + [
            "-q", "repoquery",
            "--queryformat=NAME:%{name}\nVERSION:%{version}\nRELEASE:%{release}\nEPOCH:%{epoch}\nEVR:%{evr}\nARCH:%{arch}\nNEVRA:%{name}-%{evr}.%{arch}\nLOCATION:%{location}\nREPOID:%{repoid}\nREQUIRES:\n%{regular_requires}\nPROVIDES:\n%{provides}\nRECOMMENDS:\n%{recommends}\n---RECORD_END---",
        ] + query_targets
        res_q = subprocess.run(q_cmd, capture_output=True, text=True)
        if res_q.returncode != 0:
            sys.stderr.write(f"dnf5 repoquery failed:\n{res_q.stderr}\n")
            sys.exit(res_q.returncode)

        all_pkgs = parse_repoquery_output(res_q.stdout)

        # Filter to only packages selected by download --url
        resolved_pkgs = {}
        resolved_urls_map = {}
        for pkg in all_pkgs:
            loc = pkg["location"]
            base_loc = os.path.basename(loc)
            for u in resolved_urls:
                if u == loc or u.endswith("/" + loc) or u == base_loc or u.endswith("/" + base_loc):
                    resolved_pkgs[pkg["name"]] = pkg
                    resolved_urls_map[pkg["name"]] = u
                    break

        # Load checksums: cachedir primary.xml first via repomd, repomd.load fallback
        checksum_map = repomd.load_cache(os.path.join(tmp_dir, "cache"))
        if not checksum_map:
            checksum_map = load_checksums_from_repomd(args.reposdir, repo_dir_abs)

        # Build dependency graph
        dep_graph = {}
        for name, pkg in resolved_pkgs.items():
            direct_deps = set()
            for req in pkg["requires"]:
                req_cap = req.split()[0]
                for other_name, other_pkg in resolved_pkgs.items():
                    if other_name == name:
                        continue
                    if other_name == req_cap or capability_matches(req, other_pkg["provides"]):
                        direct_deps.add(other_name)
            dep_graph[name] = sorted(direct_deps)

        # Transitive dependencies for topological sorting
        trans_graph = {}
        for name in resolved_pkgs:
            trans = set()
            stack = list(dep_graph.get(name, []))
            while stack:
                n = stack.pop()
                if n not in trans:
                    trans.add(n)
                    stack.extend(dep_graph.get(n, []))
            trans_graph[name] = sorted(trans)

        sorted_names = sorted(resolved_pkgs.keys(), key=lambda n: (len(trans_graph[n]), n))

        output_packages = []
        for name in sorted_names:
            pkg = resolved_pkgs[name]
            loc = pkg["location"]
            chk_info = checksum_map.get(loc) or checksum_map.get(os.path.basename(loc))
            chk = chk_info[0] if chk_info else ""
            integrity = ("sha256-" + base64.b64encode(bytes.fromhex(chk)).decode()) if chk else ""

            url = resolved_urls_map.get(name, loc)
            if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://"):
                url = "file://${repo_dir}/" + loc

            pkg_obj = {
                "name": pkg["name"],
                "version": pkg["evr"],
                "arch": pkg["arch"],
                "nevra": pkg["nevra"],
                "url": url,
                "integrity": integrity,
                "checksum": chk,
                "dependencies": dep_graph.get(name, []),
            }
            if pkg["recommends"]:
                pkg_obj["recommends"] = sorted(pkg["recommends"])
            output_packages.append(pkg_obj)

        lockfile_data = {
            "version": 1,
            "arch": args.arch,
            "requested": sorted(args.packages),
            "packages": output_packages,
        }

        json_text = json.dumps(lockfile_data, indent=2, separators=(",", ":"))
        json_text = json_text.replace("/", "\\/") + "\n"

        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_text)


if __name__ == "__main__":
    main()
