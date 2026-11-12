#!/usr/bin/env python3
"""Deduplicates directory and file entries in an uncompressed tar archive, resolves symlinked parents, and filters locales."""

import argparse
import os
import sys
import tarfile


def normalize_entry_name(name: str) -> str:
    """Strips leading './' and trailing '/' to obtain a canonical entry name."""
    while name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


def parse_install_langs(val: str | None) -> set[str] | None:
    """Parses install_langs string (e.g. 'en_US.UTF-8', 'en_US:en') into allowed language tokens.

    Returns None if no filtering should be applied (e.g. empty or 'all').
    """
    if not val or val.strip().lower() == "all":
        return None
    raw_tokens = [tok.strip().lower() for tok in val.replace(",", ":").split(":") if tok.strip()]
    if not raw_tokens or "all" in raw_tokens:
        return None

    allowed = {"c", "posix"}
    for tok in raw_tokens:
        allowed.add(tok)
        # Strip character encoding (e.g. .utf-8, .utf8)
        base = tok.split(".")[0]
        allowed.add(base)
        # Strip modifier (e.g. @quot, @boldquot, @euro)
        base_no_mod = base.split("@")[0]
        allowed.add(base_no_mod)
        # Base language code (e.g. en from en_us)
        lang_only = base_no_mod.split("_")[0]
        allowed.add(lang_only)
    return allowed


def should_keep_locale(norm: str, allowed_langs: set[str] | None) -> bool:
    """Determines whether a file or directory should be kept based on allowed languages.

    Applies to entries under usr/share/locale/ and usr/lib/locale/.
    Non-locale paths, root locale directories, locale.alias, and base C/POSIX locales are always kept.
    """
    if allowed_langs is None:
        return True

    p = norm.lstrip("/")
    for prefix in ("usr/share/locale/", "usr/lib/locale/"):
        if p.startswith(prefix):
            rel = p[len(prefix):]
            if not rel or rel == "locale.alias" or rel == "locale-archive":
                return True
            parts = rel.split("/", 1)
            loc_dir = parts[0].lower()
            loc_base = loc_dir.split(".")[0]
            loc_base_no_mod = loc_base.split("@")[0]
            loc_lang = loc_base_no_mod.split("_")[0]
            if (
                loc_dir in allowed_langs
                or loc_base in allowed_langs
                or loc_base_no_mod in allowed_langs
                or loc_lang in allowed_langs
            ):
                return True
            return False
    return True


def resolve_dir(dir_path: str, symlink_map: dict[str, str], max_hops: int = 32) -> str:
    """Resolves a directory path by dereferencing intermediate symlink components.

    Symlink targets that are relative are resolved relative to the directory containing the symlink.
    Symlink targets that are absolute are resolved relative to the archive root.
    """
    if not dir_path or dir_path == ".":
        return ""
    components = [c for c in dir_path.split("/") if c and c != "."]
    resolved: list[str] = []
    hops = 0

    i = 0
    while i < len(components):
        comp = components[i]
        i += 1

        if comp == "..":
            if resolved:
                resolved.pop()
            continue

        resolved.append(comp)
        current = "/".join(resolved)

        if current in symlink_map:
            hops += 1
            if hops > max_hops:
                raise ValueError(f"Symlink cycle detected resolving directory '{dir_path}'")

            target = symlink_map[current]
            resolved.pop()

            if target.startswith("/"):
                target_parts = [c for c in target.split("/") if c and c != "."]
                resolved = []
                components = target_parts + components[i:]
                i = 0
            else:
                target_parts = [c for c in target.split("/") if c and c != "."]
                components = target_parts + components[i:]
                i = 0

    return "/".join(resolved)


def canonicalize_path(norm: str, symlink_map: dict[str, str]) -> str:
    """Canonicalizes an entry path by resolving parent directories that are symlinks."""
    if not norm or norm == ".":
        return norm

    if "/" not in norm:
        return norm

    parent, basename = norm.rsplit("/", 1)
    resolved_parent = resolve_dir(parent, symlink_map)
    if resolved_parent:
        return f"{resolved_parent}/{basename}"
    return basename


def build_symlink_map(src: tarfile.TarFile) -> dict[str, str]:
    """Collects all symbolic links from the archive and indexes their canonical paths."""
    raw_symlinks: dict[str, str] = {}
    for member in src:
        if member.issym():
            name = normalize_entry_name(member.name)
            if name:
                raw_symlinks[name] = member.linkname

    symlinks: dict[str, str] = dict(raw_symlinks)
    for name, target in raw_symlinks.items():
        if "/" in name:
            canon = canonicalize_path(name, symlinks)
            if canon != name:
                symlinks[canon] = target

    return symlinks


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate entries in a tar archive.")
    parser.add_argument("--input", required=True, help="Path to input uncompressed tar archive")
    parser.add_argument("--output", required=True, help="Path to output deduplicated tar archive")
    parser.add_argument(
        "--install-langs",
        default="",
        help="Language locales to keep (e.g. 'en_US.UTF-8'), filtering non-matching locale files",
    )
    args = parser.parse_args()

    allowed_langs = parse_install_langs(args.install_langs)

    try:
        with tarfile.open(args.input, mode="r:") as src:
            symlinks = build_symlink_map(src)

        seen_entries: dict[str, str] = {}
        seen_parent_dirs: set[str] = set()

        with tarfile.open(args.input, mode="r:") as src, \
             tarfile.open(args.output, mode="w:") as dst:
            for member in src:
                norm = normalize_entry_name(member.name)

                if member.isdir():
                    canon = resolve_dir(norm, symlinks) if norm not in ("", ".") else "."
                else:
                    canon = canonicalize_path(norm, symlinks)

                if not should_keep_locale(canon, allowed_langs):
                    continue

                if not canon or canon == ".":
                    if "." in seen_entries:
                        continue
                    seen_entries["."] = "dir"
                    member.name = "."
                    dst.addfile(member)
                    continue

                curr_type = "dir" if member.isdir() else "file"

                # Check for directory vs file type conflict with an already registered entry
                if canon in seen_entries:
                    prev_type = seen_entries[canon]
                    if prev_type != curr_type:
                        raise ValueError(
                            f"Type conflict for entry '{canon}': cannot overwrite {prev_type} with {curr_type}"
                        )
                    continue

                # Check ancestor conflict: no parent path of a new entry can be an existing file
                parts = canon.split("/")
                for j in range(1, len(parts)):
                    ancestor = "/".join(parts[:j])
                    if ancestor in seen_entries and seen_entries[ancestor] != "dir":
                        raise ValueError(
                            f"Type conflict: parent path '{ancestor}' of entry '{canon}' is a {seen_entries[ancestor]}, not a directory"
                        )
                    seen_parent_dirs.add(ancestor)

                # A regular file cannot overwrite a path already used as a parent directory
                if curr_type == "file" and canon in seen_parent_dirs:
                    raise ValueError(
                        f"Type conflict: path '{canon}' is a file but was already used as a directory"
                    )

                seen_entries[canon] = curr_type
                member.name = canon

                if member.islnk():
                    link_norm = normalize_entry_name(member.linkname)
                    member.linkname = canonicalize_path(link_norm, symlinks)

                if member.isreg():
                    with src.extractfile(member) as f:
                        dst.addfile(member, fileobj=f)
                else:
                    dst.addfile(member)

        return 0

    except Exception as e:
        if os.path.exists(args.output):
            try:
                os.remove(args.output)
            except OSError:
                pass
        sys.stderr.write(f"Error deduplicating tar archive: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
