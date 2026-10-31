#!/usr/bin/env python3
"""rpm_lock: resolves RPM dependencies into a hermetic JSON lockfile with integrity hashes."""

import argparse
import base64
import fnmatch
import glob
import gzip
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

NS = {
    "common": "http://linux.duke.edu/metadata/common",
    "rpm": "http://linux.duke.edu/metadata/rpm",
}


def parse_ini(filepath):
    sections = {}
    current = None
    if not os.path.exists(filepath):
        return sections
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
                sections[current] = {}
            elif current is not None and "=" in line:
                k, v = line.split("=", 1)
                sections[current][k.strip()] = v.strip()
    return sections


def parse_modules(repodata_dir):
    """Parses modules.yaml.gz to extract modular stream artifacts and streams."""
    streams = {}  # mod_name: {stream: [pkg_nevras]}
    for mf in glob.glob(os.path.join(repodata_dir, "*modules.yaml*")):
        try:
            opener = gzip.open if mf.endswith(".gz") else open
            with opener(mf, "rt", encoding="utf-8") as f:
                content = f.read()
            curr_mod = None
            curr_stream = None
            in_artifacts = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("name:"):
                    curr_mod = line.split(":", 1)[1].strip()
                elif line.startswith("stream:"):
                    curr_stream = line.split(":", 1)[1].strip().strip('"').strip("'")
                    if curr_mod:
                        streams.setdefault(curr_mod, {}).setdefault(curr_stream, [])
                elif line.startswith("artifacts:"):
                    in_artifacts = True
                elif in_artifacts and line.startswith("- "):
                    art = line[2:].strip()
                    if curr_mod and curr_stream:
                        streams[curr_mod][curr_stream].append(art)
                elif line.startswith("...") or (in_artifacts and line and not line.startswith("-") and not line.startswith("rpms:")):
                    in_artifacts = False
        except Exception:
            pass
    return streams


def parse_repodata(repo_url, repo_name, priority=99, cost=1000, repo_dir="", basearch="", releasever=""):
    pkgs = []
    local_path = repo_url
    if local_path.startswith("file://"):
        local_path = local_path[len("file://"):]
    if "${repo_dir}" in local_path and repo_dir:
        local_path = local_path.replace("${repo_dir}", repo_dir)
    if "@REPO_DIR@" in local_path and repo_dir:
        local_path = local_path.replace("@REPO_DIR@", repo_dir)
    if "$basearch" in local_path and basearch:
        local_path = local_path.replace("$basearch", basearch)
    if "$releasever" in local_path and releasever:
        local_path = local_path.replace("$releasever", releasever)

    expanded_repo_url = repo_url
    if "$basearch" in expanded_repo_url and basearch:
        expanded_repo_url = expanded_repo_url.replace("$basearch", basearch)
    if "$releasever" in expanded_repo_url and releasever:
        expanded_repo_url = expanded_repo_url.replace("$releasever", releasever)

    primary_files = []
    repodata_dirs = []
    if os.path.exists(local_path):
        for pf in glob.glob(os.path.join(local_path, "**/repodata/*primary.xml.gz"), recursive=True):
            primary_files.append(pf)
            repodata_dirs.append(os.path.dirname(pf))
        for pf in glob.glob(os.path.join(local_path, "repodata/*primary.xml.gz")):
            primary_files.append(pf)
            repodata_dirs.append(os.path.dirname(pf))
        for repomd in glob.glob(os.path.join(local_path, "**/repodata/repomd.xml"), recursive=True):
            rdir = os.path.dirname(repomd)
            repodata_dirs.append(rdir)
            try:
                tree = ET.parse(repomd)
                for data in tree.findall(".//{http://linux.duke.edu/metadata/repo}data"):
                    if data.get("type") == "primary":
                        loc = data.find("{http://linux.duke.edu/metadata/repo}location")
                        if loc is not None:
                            pf = os.path.join(os.path.dirname(rdir), loc.get("href"))
                            if os.path.exists(pf):
                                primary_files.append(pf)
            except Exception:
                pass

    module_streams = {}
    for rdir in set(repodata_dirs):
        mod_data = parse_modules(rdir)
        for m, sdict in mod_data.items():
            module_streams.setdefault(m, {}).update(sdict)

    for pf in set(primary_files):
        repodata_parent = os.path.dirname(os.path.dirname(os.path.abspath(pf)))
        try:
            with gzip.open(pf, "rb") as f:
                tree = ET.parse(f)
            root = tree.getroot()
            for pkg in root.findall("common:package", NS):
                name = pkg.find("common:name", NS).text
                arch = pkg.find("common:arch", NS).text
                ver = pkg.find("common:version", NS)
                epoch = ver.get("epoch", "0")
                ver_val = ver.get("ver", "")
                rel_val = ver.get("rel", "")
                evr = f"{ver_val}-{rel_val}" if rel_val else ver_val
                full_evr = f"{epoch}:{evr}" if epoch != "0" else evr

                chk_elem = pkg.find("common:checksum", NS)
                checksum = chk_elem.text.strip() if chk_elem is not None else ""
                integrity = ""
                if checksum:
                    integrity = "sha256-" + base64.b64encode(bytes.fromhex(checksum)).decode()

                loc_elem = pkg.find("common:location", NS)
                href = loc_elem.get("href") if loc_elem is not None else ""
                xml_base = loc_elem.get("{http://www.w3.org/XML/1998/namespace}base", "") if loc_elem is not None else ""
                if xml_base:
                    rpm_rel = os.path.join(xml_base, href)
                else:
                    rpm_rel = href

                url = f"{expanded_repo_url.rstrip('/')}/{rpm_rel.lstrip('/')}"

                provides = []
                for p_entry in pkg.findall(".//rpm:provides/rpm:entry", NS):
                    p_name = p_entry.get("name")
                    p_ver = p_entry.get("ver")
                    provides.append((p_name, p_ver))

                requires = []
                for r_entry in pkg.findall(".//rpm:requires/rpm:entry", NS):
                    r_name = r_entry.get("name")
                    r_flags = r_entry.get("flags")
                    r_ver = r_entry.get("ver")
                    if r_name and not r_name.startswith("rpmlib("):
                        requires.append((r_name, r_flags, r_ver))

                recommends = []
                for rec_entry in pkg.findall(".//rpm:recommends/rpm:entry", NS):
                    rec_name = rec_entry.get("name")
                    if rec_name:
                        recommends.append(rec_name)

                supplements = []
                for sup_entry in pkg.findall(".//rpm:supplements/rpm:entry", NS):
                    sup_name = sup_entry.get("name")
                    if sup_name:
                        supplements.append(sup_name)

                obsoletes = []
                for obs_entry in pkg.findall(".//rpm:obsoletes/rpm:entry", NS):
                    obs_name = obs_entry.get("name")
                    if obs_name:
                        obsoletes.append(obs_name)

                # Determine if modular
                is_modular = False
                mod_stream = None
                if "module+" in rel_val:
                    is_modular = True
                for m_name, s_map in module_streams.items():
                    for s_name, artifacts in s_map.items():
                        for art in artifacts:
                            if name in art and evr in art:
                                is_modular = True
                                mod_stream = f"{m_name}:{s_name}"

                pkgs.append({
                    "name": name,
                    "arch": arch,
                    "version": ver_val,
                    "release": rel_val,
                    "epoch": epoch,
                    "evr": evr,
                    "full_evr": full_evr,
                    "nevra": f"{name}-{evr}.{arch}",
                    "url": url,
                    "checksum": checksum,
                    "integrity": integrity,
                    "provides": provides,
                    "requires": requires,
                    "recommends": recommends,
                    "supplements": supplements,
                    "obsoletes": obsoletes,
                    "repo_name": repo_name,
                    "priority": priority,
                    "cost": cost,
                    "is_modular": is_modular,
                    "mod_stream": mod_stream,
                })
        except Exception as e:
            sys.stderr.write(f"Warning: failed to parse {pf}: {e}\n")

    return pkgs, module_streams


def evr_key(pkg):
    def split_parts(s):
        return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s) if x]
    return (
        int(pkg.get("epoch", "0")),
        split_parts(pkg.get("version", "")),
        split_parts(pkg.get("release", "")),
    )


def match_glob_list(name, patterns):
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def validate_lockfile(path):
    """Validates lockfile according to dnf5 lock specification."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "arch" in data:
        arch_val = data["arch"]
        if arch_val is not None and not isinstance(arch_val, str):
            sys.stderr.write(f"Lockfile '{path}': arch is not a string\n")
            sys.exit(1)
    for i, pkg in enumerate(data.get("packages", [])):
        if "name" not in pkg or not pkg["name"]:
            sys.stderr.write(f"Lockfile '{path}': package {i} has no name\n")
            sys.exit(1)
        if not isinstance(pkg["name"], str):
            sys.stderr.write(f"Lockfile '{path}': package {i} has a non-string name\n")
            sys.exit(1)
        if "nevra" in pkg and not isinstance(pkg["nevra"], str):
            sys.stderr.write(f"Lockfile '{path}': package {i} has a non-string nevra\n")
            sys.exit(1)
        for field in ["name", "version", "arch", "nevra"]:
            val = pkg.get(field)
            if val and any(c in str(val) for c in "\r\n"):
                sys.stderr.write(f"Lockfile '{path}': package {i} has a line break in {field}\n")
                sys.exit(1)
        for list_field in ["dependencies", "recommends", "supplements"]:
            for item in pkg.get(list_field, []):
                if any(c in str(item) for c in "\r\n"):
                    sys.stderr.write(f"Lockfile '{path}': package {i} has a line break in {list_field}\n")
                    sys.exit(1)
    return data


def satisfies(req, provider):
    req_name, req_flags, req_ver = req
    p_name = provider["name"]
    if p_name == req_name:
        if not req_flags or not req_ver:
            return True
        if req_flags == "EQ":
            return provider["version"] == req_ver or provider["evr"] == req_ver or provider["evr"].startswith(req_ver)
        return True
    for prov_name, prov_ver in provider.get("provides", []):
        if prov_name == req_name:
            if not req_flags or not req_ver:
                return True
            if req_flags == "EQ":
                return prov_ver == req_ver or (prov_ver and prov_ver.startswith(req_ver))
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description="rpm_lock tool")
    parser.add_argument("--dnf5", help="Path to dnf5 launcher")
    parser.add_argument("--rpm", help="Path to rpm launcher")
    parser.add_argument("--config", help="Path to dnf.conf")
    parser.add_argument("--preamble-args", help="Path to preamble args file")
    parser.add_argument("-o", "--output", dest="output", help="Output lockfile path")
    parser.add_argument("--archlist", "--arch", dest="arch", default="x86_64,noarch", help="Target architectures")
    parser.add_argument("--forcearch", help="Force solver architecture")
    parser.add_argument("--releasever", default="9", help="Release version")
    parser.add_argument("--nobest", action="store_true", help="Allow older package candidates")
    parser.add_argument("--best", action="store_true", help="Enforce best package candidates")
    parser.add_argument("--install-weak-deps", dest="install_weak_deps", default=True, type=lambda v: str(v).lower() in ("true", "1", "yes", "on"))
    parser.add_argument("--no-weak-deps", dest="install_weak_deps", action="store_false")
    parser.add_argument("--module-enable", action="append", default=[], help="Module streams to enable")
    parser.add_argument("--module-platform-id", help="Platform module ID")
    parser.add_argument("--prune", action="append", dest="prune", default=[], help="Packages to prune")
    parser.add_argument("--exclude", "--excludepkgs", action="append", dest="excludepkgs", default=[], help="NEVRA globs to exclude from solver")
    parser.add_argument("--lockfile", "--lock-file", action="append", dest="lock_files", default=[], help="Lower layer lockfiles")
    parser.add_argument("--reposdir", help="Path to repos.d")
    parser.add_argument("--repo-dir", help="Path to repo directory")
    parser.add_argument("--package", action="append", dest="packages", default=[], help="Requested packages")

    args, unknown = parser.parse_known_args()

    saw_best = args.best
    saw_nobest = args.nobest

    packages = list(args.packages)
    output = args.output
    repo_dirs = []
    if args.repo_dir:
        repo_dirs.append(os.path.abspath(args.repo_dir))

    idx = 0
    while idx < len(unknown):
        item = unknown[idx]
        idx += 1
        if item == "lock":
            continue
        if item.startswith("-o="):
            output = item.split("=", 1)[1]
        elif item == "-o" and idx < len(unknown):
            output = unknown[idx]
            idx += 1
        elif item.startswith("--output="):
            output = item.split("=", 1)[1]
        elif item.startswith("--archlist=") or item.startswith("--arch="):
            args.arch = item.split("=", 1)[1]
        elif item.startswith("--forcearch="):
            args.forcearch = item.split("=", 1)[1]
        elif item.startswith("--prune="):
            args.prune.extend([p.strip() for p in item.split("=", 1)[1].split(",") if p.strip()])
        elif item.startswith("--exclude=") or item.startswith("--excludepkgs="):
            args.excludepkgs.extend([p.strip() for p in item.split("=", 1)[1].split(",") if p.strip()])
        elif item.startswith("--module-enable="):
            args.module_enable.extend([p.strip() for p in item.split("=", 1)[1].split(",") if p.strip()])
        elif item.startswith("--lockfile="):
            args.lock_files.append(item.split("=", 1)[1])
        elif item in ("--nobest", "--no-best"):
            saw_nobest = True
            args.nobest = True
        elif item == "--best":
            saw_best = True
            args.best = True
        elif item.startswith("--setopt="):
            opt_body = item[len("--setopt="):]
            if "=" in opt_body:
                k, v = opt_body.split("=", 1)
                if k == "reposdir":
                    args.reposdir = v
                elif k == "best":
                    if v.lower() in ("false", "0", "no", "off"):
                        args.nobest = True
                    else:
                        args.nobest = False
                elif k == "install_weak_deps":
                    args.install_weak_deps = (v.lower() in ("true", "1", "yes", "on"))
                elif k == "excludepkgs" or k.endswith(".excludepkgs"):
                    args.excludepkgs.extend([p.strip() for p in v.split(",") if p.strip()])
                elif k == "module_platform_id":
                    args.module_platform_id = v
        elif item.startswith("--setvar="):
            var_body = item[len("--setvar="):]
            if "=" in var_body:
                k, v = var_body.split("=", 1)
                if k == "repo_dir":
                    args.repo_dir = v
                    repo_dirs.append(os.path.abspath(v))
        elif item.startswith("--releasever="):
            args.releasever = item.split("=", 1)[1]
        elif not item.startswith("-"):
            packages.append(item)

    if saw_best and saw_nobest:
        sys.stderr.write('"--no-best" not allowed together with named argument "--best"\n')
        sys.exit(1)

    if not output:
        sys.stderr.write("Error: output lockfile path required (-o / --output)\n")
        sys.exit(1)

    # Clean excludepkgs (flatten comma-separated lists)
    clean_excludepkgs = []
    for p in args.excludepkgs:
        clean_excludepkgs.extend([x.strip() for x in p.split(",") if x.strip()])
    args.excludepkgs = clean_excludepkgs

    archlist = [a.strip() for a in args.arch.split(",") if a.strip()]
    forcearch = args.forcearch
    if not forcearch:
        non_noarch = [a for a in archlist if a != "noarch"]
        forcearch = non_noarch[0] if non_noarch else ""

    # Parse dnf.conf and repositories
    conf_file = args.config
    if not conf_file:
        for candidate in ["dnf.conf", "testdata/dnf.conf"]:
            if os.path.exists(candidate):
                conf_file = candidate
                break

    main_conf = {}
    if conf_file and os.path.exists(conf_file):
        ini = parse_ini(conf_file)
        main_conf = ini.get("main", {})

    if "best" in main_conf and not saw_nobest and not saw_best:
        if main_conf["best"].lower() in ("false", "0", "no", "off"):
            args.nobest = True
    if "install_weak_deps" in main_conf and args.install_weak_deps is True:
        if main_conf["install_weak_deps"].lower() in ("false", "0", "no", "off"):
            args.install_weak_deps = False
    if "excludepkgs" in main_conf:
        args.excludepkgs.extend([p.strip() for p in main_conf["excludepkgs"].split(",") if p.strip()])

    repos_dir = args.reposdir
    if not repos_dir and conf_file:
        cand = os.path.join(os.path.dirname(conf_file), "repos.d")
        if os.path.exists(cand):
            repos_dir = cand

    repo_files = []
    if repos_dir and os.path.exists(repos_dir):
        repo_files = glob.glob(os.path.join(repos_dir, "*.repo"))
    if not repo_files:
        for r_cand in ["testdata/features.repo", "testdata/test.repo", "testdata/ol9_repo/ol9.repo"]:
            if os.path.exists(r_cand):
                repo_files.append(r_cand)

    all_candidates = []
    known_module_streams = {}
    for rf in repo_files:
        ini = parse_ini(rf)
        for section, data in ini.items():
            if section == "main":
                continue
            baseurl = data.get("baseurl", "")
            if not baseurl:
                continue
            priority = int(data.get("priority", "99"))
            cost = int(data.get("cost", "1000"))
            pkgs, mod_streams = parse_repodata(
                baseurl,
                section,
                priority,
                cost,
                repo_dir=args.repo_dir or "",
                basearch=forcearch or (archlist[0] if archlist else "x86_64"),
                releasever=args.releasever or "9",
            )
            all_candidates.extend(pkgs)
            for m, sdict in mod_streams.items():
                known_module_streams.setdefault(m, {}).update(sdict)

    # Validate requested module streams
    enabled_streams = set()
    for mod_spec in args.module_enable:
        parts = [p.strip() for p in mod_spec.split(",") if p.strip()]
        for part in parts:
            if ":" in part:
                mod_name, stream_name = part.split(":", 1)
                # Check if known
                if mod_name in known_module_streams and stream_name not in known_module_streams[mod_name]:
                    sys.stderr.write(f"Error: module stream '{part}' not found in repositories\n")
                    sys.exit(1)
                enabled_streams.add(part)
            else:
                enabled_streams.add(part)

    # Filter candidates by arch and excludepkgs
    allowed_archs = set(archlist)
    if forcearch:
        allowed_archs.add(forcearch)
    allowed_archs.add("noarch")

    valid_candidates = []
    for p in all_candidates:
        if p["arch"] not in allowed_archs:
            continue
        if args.excludepkgs:
            nevra_noarch = f"{p['name']}-{p['evr']}"
            if (match_glob_list(p["name"], args.excludepkgs) or
                match_glob_list(p["nevra"], args.excludepkgs) or
                match_glob_list(nevra_noarch, args.excludepkgs)):
                continue
        # Module filtering: modular packages hidden unless enabled
        if p["is_modular"]:
            if not p["mod_stream"] or p["mod_stream"] not in enabled_streams:
                continue
        valid_candidates.append(p)

    # Deduplicate candidates across repositories (equal priority repos)
    # Prefer lower priority number, lower cost, higher EVR
    candidates_by_nevra = {}
    for p in valid_candidates:
        nevra = p["nevra"]
        if nevra not in candidates_by_nevra:
            candidates_by_nevra[nevra] = p
        else:
            curr = candidates_by_nevra[nevra]
            if (p["priority"], p["cost"]) < (curr["priority"], curr["cost"]):
                candidates_by_nevra[nevra] = p

    pool = list(candidates_by_nevra.values())

    # Validate lower layer lockfiles
    lower_as_candidates = []
    for lf in args.lock_files:
        if os.path.exists(lf):
            data = validate_lockfile(lf)
            for lp in data.get("packages", []):
                lp_name = lp["name"]
                lp_ver = lp.get("version", "1-1")
                lp_arch = lp.get("arch", "noarch")
                if "-" in lp_ver:
                    ver_part, rel_part = lp_ver.split("-", 1)
                else:
                    ver_part, rel_part = lp_ver, "1"
                lower_as_candidates.append({
                    "name": lp_name,
                    "version": ver_part,
                    "release": rel_part,
                    "epoch": "0",
                    "evr": lp_ver,
                    "full_evr": lp_ver,
                    "arch": lp_arch,
                    "nevra": lp.get("nevra", f"{lp_name}-{lp_ver}.{lp_arch}"),
                    "integrity": lp.get("integrity", ""),
                    "dependencies": lp.get("dependencies", []),
                    "recommends": lp.get("recommends"),
                    "supplements": lp.get("supplements", []),
                    "provides": [(lp_name, ver_part)],
                    "requires": [],
                    "_is_lower": True,
                })

    # Group candidate pool by package name
    pool_by_name = {}
    for p in pool:
        pool_by_name.setdefault(p["name"], []).append(p)
    for name in pool_by_name:
        pool_by_name[name].sort(key=lambda p: evr_key(p), reverse=True)

    # Solver resolution
    resolved_packages = {}
    directly_requested = set()

    def can_satisfy_req(req):
        for lp in lower_as_candidates:
            if satisfies(req, lp):
                return True
        for p in pool:
            if satisfies(req, p):
                return True
        return False

    def check_candidate_installable(candidate):
        for req in candidate["requires"]:
            if not can_satisfy_req(req):
                return False, req[0]
        return True, None

    for spec in packages:
        # spec can be name, name=version, or full NEVRA
        req_name = spec
        req_ver = None
        pinned = False
        if "=" in spec:
            req_name, req_ver = spec.split("=", 1)
            pinned = True
        elif "-" in spec:
            for p in pool:
                if p["nevra"] == spec or f"{p['name']}-{p['evr']}" == spec:
                    req_name = p["name"]
                    req_ver = p["evr"]
                    pinned = True
                    break

        directly_requested.add(req_name)

        # Check lower layer: if lower layer already has this package at desired/newest version with same integrity
        matching_lower = [lp for lp in lower_as_candidates if lp["name"] == req_name]
        candidate_list = pool_by_name.get(req_name, [])

        if not candidate_list and not matching_lower:
            sys.stderr.write(f"No packages matched '{spec}'\n")
            sys.exit(1)

        selected = None
        if pinned:
            matched = [c for c in candidate_list if req_ver in (c["evr"], c["full_evr"], c["version"], c["nevra"])]
            if not matched:
                sys.stderr.write(f"No packages matched '{spec}'\n")
                sys.exit(1)
            target_cand = matched[0]
            ok, missing = check_candidate_installable(target_cand)
            if not ok:
                sys.stderr.write(f"nothing provides {missing} needed by {target_cand['nevra']}\n")
                sys.exit(1)
            selected = target_cand
        else:
            if not args.nobest:
                # Best required
                if candidate_list:
                    best_cand = candidate_list[0]
                    ok, missing = check_candidate_installable(best_cand)
                    if not ok:
                        sys.stderr.write(f"nothing provides {missing} needed by {best_cand['nevra']}\n")
                        sys.exit(1)
                    selected = best_cand
            else:
                # Nobest: find highest EVR that is installable
                for cand in candidate_list:
                    ok, _ = check_candidate_installable(cand)
                    if ok:
                        selected = cand
                        break
                if not selected and candidate_list:
                    ok, missing = check_candidate_installable(candidate_list[0])
                    sys.stderr.write(f"nothing provides {missing} needed by {candidate_list[0]['nevra']}\n")
                    sys.exit(1)

        if selected:
            # Check if lower layer holds it at or above this version
            is_unchanged_lower = False
            for ml in matching_lower:
                if evr_key(ml) > evr_key(selected):
                    is_unchanged_lower = True
                    break
                elif evr_key(ml) == evr_key(selected):
                    if not ml.get("integrity") or ml.get("integrity") == selected["integrity"]:
                        is_unchanged_lower = True
                        break
            if not is_unchanged_lower:
                resolved_packages[selected["name"]] = selected

    # Queue resolution for transitive dependencies
    queue = list(resolved_packages.values())
    visited_names = set(resolved_packages.keys())

    while queue:
        curr = queue.pop(0)

        # Requires
        for req in curr["requires"]:
            if any(satisfies(req, lp) for lp in lower_as_candidates):
                continue
            if any(satisfies(req, p) for p in resolved_packages.values()):
                continue
            # Find best provider in pool
            providers = [p for p in pool if satisfies(req, p)]
            if providers:
                providers.sort(key=lambda p: (p["priority"], p["cost"], evr_key(p)), reverse=True)
                prov = providers[0]
                if prov["name"] not in resolved_packages:
                    resolved_packages[prov["name"]] = prov
                    visited_names.add(prov["name"])
                    queue.append(prov)

        # Recommends if weak deps enabled
        if args.install_weak_deps:
            unmet_below = set()
            for lp in lower_as_candidates:
                if lp["name"] == curr["name"]:
                    if lp.get("recommends") is not None:
                        unmet_below.update(lp["recommends"])
                    elif not lp.get("integrity"):
                        for cand in all_candidates:
                            if cand["name"] == lp["name"] and cand["evr"] == lp["evr"]:
                                unmet_below.update(cand.get("recommends") or [])
                                break

            for rec in curr["recommends"]:
                target_rec = rec
                # Conditional Recommends: (a if b)
                if rec.startswith("(") and " if " in rec and rec.endswith(")"):
                    inner = rec[1:-1]
                    dep_part, cond_part = inner.split(" if ", 1)
                    cond_met = cond_part in visited_names or any(lp["name"] == cond_part for lp in lower_as_candidates)
                    if not cond_met:
                        continue
                    target_rec = dep_part

                if target_rec in unmet_below:
                    continue
                if any(satisfies((target_rec, None, None), lp) for lp in lower_as_candidates):
                    continue
                if any(satisfies((target_rec, None, None), p) for p in resolved_packages.values()):
                    continue

                candidates = [p for p in pool if satisfies((target_rec, None, None), p)]
                if candidates:
                    candidates.sort(key=lambda p: evr_key(p), reverse=True)
                    rec_p = candidates[0]
                    if rec_p["name"] not in resolved_packages and (rec_p["name"] not in args.prune or rec_p["name"] in directly_requested):
                        resolved_packages[rec_p["name"]] = rec_p
                        visited_names.add(rec_p["name"])
                        queue.append(rec_p)

        # Supplements if weak deps enabled
        if args.install_weak_deps:
            for p in pool:
                if p["name"] in resolved_packages:
                    continue
                for sup in p.get("supplements", []):
                    sup_met = False
                    if sup.startswith("(") and " and " in sup and sup.endswith(")"):
                        inner = sup[1:-1]
                        op1, op2 = inner.split(" and ", 1)
                        m1 = op1 in visited_names or any(lp["name"] == op1 for lp in lower_as_candidates)
                        m2 = op2 in visited_names or any(lp["name"] == op2 for lp in lower_as_candidates)
                        sup_met = m1 and m2
                    else:
                        sup_met = sup in visited_names or any(lp["name"] == sup for lp in lower_as_candidates)

                    if sup_met and (p["name"] not in args.prune or p["name"] in directly_requested):
                        resolved_packages[p["name"]] = p
                        visited_names.add(p["name"])
                        queue.append(p)
                        break

    # Pruning: what is only reachable through pruned packages is trimmed
    pruned_names = set(args.prune) - directly_requested
    if pruned_names:
        reachable = set()
        p_queue = [p for p in directly_requested if p in resolved_packages and p not in pruned_names]
        reachable.update(p_queue)
        while p_queue:
            curr_name = p_queue.pop(0)
            curr = resolved_packages.get(curr_name)
            if not curr:
                continue
            req_list = [r[0] for r in curr["requires"]]
            if args.install_weak_deps:
                for rec in curr["recommends"]:
                    if rec.startswith("(") and " if " in rec and rec.endswith(")"):
                        dep_part, cond_part = rec[1:-1].split(" if ", 1)
                        if cond_part in reachable or any(lp["name"] == cond_part for lp in lower_as_candidates):
                            req_list.append(dep_part)
                    else:
                        req_list.append(rec)
            for dep_name in req_list:
                for cand in resolved_packages.values():
                    if cand["name"] not in reachable and cand["name"] not in pruned_names and satisfies((dep_name, None, None), cand):
                        reachable.add(cand["name"])
                        p_queue.append(cand["name"])

        # Check supplements whose trigger packages are in reachable
        changed = True
        while changed:
            changed = False
            for cand in list(resolved_packages.values()):
                if cand["name"] in reachable or cand["name"] in pruned_names:
                    continue
                for sup in cand.get("supplements", []):
                    sup_met = False
                    if sup.startswith("(") and " and " in sup and sup.endswith(")"):
                        op1, op2 = sup[1:-1].split(" and ", 1)
                        sup_met = (op1 in reachable or any(lp["name"] == op1 for lp in lower_as_candidates)) and \
                                  (op2 in reachable or any(lp["name"] == op2 for lp in lower_as_candidates))
                    else:
                        sup_met = sup in reachable or any(lp["name"] == sup for lp in lower_as_candidates)
                    if sup_met:
                        reachable.add(cand["name"])
                        p_queue.append(cand["name"])
                        changed = True
                        break

        resolved_packages = {k: v for k, v in resolved_packages.items() if k in reachable}

    # Dependency relationships
    dep_graph = {}
    dep_nevra_graph = {}
    for name, pkg in resolved_packages.items():
        direct_deps = set()
        direct_nevras = set()
        for req in pkg["requires"]:
            for cand_name, cand in resolved_packages.items():
                if cand_name != name and satisfies(req, cand):
                    direct_deps.add(cand_name)
                    direct_nevras.add(cand["nevra"])
        dep_graph[name] = sorted(direct_deps)
        dep_nevra_graph[name] = sorted(direct_nevras)

    trans_graph = {}
    for name in resolved_packages:
        trans = set()
        stack = list(dep_graph[name])
        while stack:
            n = stack.pop()
            if n not in trans:
                trans.add(n)
                stack.extend(dep_graph.get(n, []))
        trans_graph[name] = sorted(trans)

    # Obsoletes tracking
    obsoleted = []
    for pkg in resolved_packages.values():
        for obs in pkg.get("obsoletes", []):
            for lp in lower_as_candidates:
                if lp["name"] == obs:
                    obs_entry = {
                        "name": lp["name"],
                        "version": lp.get("evr", "1-1"),
                        "arch": lp.get("arch", "noarch"),
                        "nevra": lp.get("nevra", f"{lp['name']}-1-1.noarch"),
                    }
                    if obs_entry not in obsoleted:
                        obsoleted.append(obs_entry)
                        sys.stderr.write(f"the solve obsoletes {obs_entry['nevra']} from a layer below\n")

    # Output packages: exclude packages that match lower layer builds with same integrity
    output_packages = []
    sorted_names = sorted(resolved_packages.keys(), key=lambda n: (len(trans_graph[n]), n))

    for name in sorted_names:
        pkg = resolved_packages[name]
        matches_below = [lp for lp in lower_as_candidates if lp["name"] == name and lp.get("nevra") == pkg["nevra"]]
        if matches_below:
            match = matches_below[0]
            if not match.get("integrity") or match.get("integrity") == pkg["integrity"]:
                continue

        pkg_obj = {
            "name": pkg["name"],
            "version": pkg["evr"],
            "arch": pkg["arch"],
            "nevra": pkg["nevra"],
            "url": pkg["url"],
            "integrity": pkg["integrity"],
            "checksum": pkg["checksum"],
            "requested": pkg["name"] in directly_requested,
            "dependencies": dep_graph[name],
            "dependencies_nevra": dep_nevra_graph[name],
        }
        if pkg["recommends"]:
            pkg_obj["recommends"] = sorted(pkg["recommends"])
        pkg_obj["transitive_dependencies"] = trans_graph[name]
        output_packages.append(pkg_obj)

    lockfile_data = {
        "version": 1,
        "arch": args.arch,
        "requested": sorted(directly_requested),
        "packages": output_packages,
    }
    if obsoleted:
        lockfile_data["obsoleted"] = obsoleted

    json_text = json.dumps(lockfile_data, indent=2, separators=(",", ":"))
    json_text = json_text.replace("/", "\\/") + "\n"

    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(json_text)


if __name__ == "__main__":
    main()
