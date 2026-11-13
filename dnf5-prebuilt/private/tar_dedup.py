#!/usr/bin/env python3
"""Deduplicates directory and file entries in an uncompressed tar or cpio newc archive, resolves symlinked parents, and filters locales."""

import argparse
from dataclasses import dataclass
import os
import stat
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


USR_MERGE_DIRS = {
    "bin": "usr/bin",
    "sbin": "usr/sbin",
    "lib": "usr/lib",
    "lib64": "usr/lib64",
}


def canonicalize_symlinks(raw_symlinks: dict[str, str]) -> dict[str, str]:
    """Indexes symlinks by both their raw and canonicalized paths."""
    symlinks: dict[str, str] = dict(raw_symlinks)
    for name, target in raw_symlinks.items():
        if "/" in name:
            canon = canonicalize_path(name, symlinks)
            if canon != name:
                symlinks[canon] = target
    return symlinks


def build_symlink_map(src: tarfile.TarFile) -> dict[str, str]:
    """Collects all symbolic links from a tar archive and indexes their canonical paths."""
    raw_symlinks: dict[str, str] = dict(USR_MERGE_DIRS)
    for member in src:
        if member.issym():
            name = normalize_entry_name(member.name)
            if name:
                raw_symlinks[name] = member.linkname
    return canonicalize_symlinks(raw_symlinks)


def resolve_canonical_name(
    raw_name: str, is_dir: bool, is_sym: bool, symlinks: dict[str, str]
) -> str:
    """Computes the canonical path of an archive entry taking into account symlinks and usr-merge."""
    norm = normalize_entry_name(raw_name)
    if norm in USR_MERGE_DIRS:
        return norm if is_sym else USR_MERGE_DIRS[norm]
    if is_dir:
        return resolve_dir(norm, symlinks) if norm not in ("", ".") else "."
    return canonicalize_path(norm, symlinks)


def get_canonical_name(member: tarfile.TarInfo, symlinks: dict[str, str]) -> str:
    """Computes the canonical path of a tar member taking into account symlinks and usr-merge."""
    return resolve_canonical_name(member.name, member.isdir(), member.issym(), symlinks)


def register_entry(
    canon: str,
    curr_type: str,
    seen_entries: dict[str, str],
    seen_parent_dirs: set[str],
) -> bool:
    """Validates type/ancestor conflicts and registers a canonical path.

    Returns True if the entry should be emitted, False if it is a duplicate directory to skip.
    Raises ValueError on directory/file type conflicts.
    """
    if canon in seen_entries:
        prev_type = seen_entries[canon]
        if prev_type != curr_type:
            raise ValueError(
                f"Type conflict for entry '{canon}': cannot overwrite {prev_type} with {curr_type}"
            )
        return False

    parts = canon.split("/")
    for j in range(1, len(parts)):
        ancestor = "/".join(parts[:j])
        if ancestor in seen_entries and seen_entries[ancestor] != "dir":
            raise ValueError(
                f"Type conflict: parent path '{ancestor}' of entry '{canon}' is a {seen_entries[ancestor]}, not a directory"
            )
        seen_parent_dirs.add(ancestor)

    if curr_type == "file" and canon in seen_parent_dirs:
        raise ValueError(
            f"Type conflict: path '{canon}' is a file but was already used as a directory"
        )

    seen_entries[canon] = curr_type
    return True


@dataclass
class CpioEntry:
    """Metadata and data offset for a single entry in a cpio newc archive."""

    idx: int
    name: str
    mode: int
    uid: int
    gid: int
    nlink: int
    mtime: int
    filesize: int
    devmajor: int
    devminor: int
    rdevmajor: int
    rdevminor: int
    ino: int
    data_offset: int
    linkname: str = ""
    group_id: int | None = None


def _flush_pending_groups(
    pending_groups: dict[tuple[int, int, int], list[CpioEntry]],
    group_data: dict[int, tuple[int, int]],
) -> None:
    """Finalizes any incomplete hard-link groups (e.g. when their data member was excluded)."""
    for group in pending_groups.values():
        gid_key = group[0].idx
        for member in group:
            member.group_id = gid_key
        group_data[gid_key] = (group[-1].data_offset, group[-1].filesize)
    pending_groups.clear()


def read_newc_entries(fp) -> tuple[list[CpioEntry], dict[int, tuple[int, int]]]:
    """Parses a cpio newc (070701/070702) stream and groups hard-link members.

    In newc, a hard-link group shares (devmajor, devminor, ino) and stores file
    contents on the last member of the group (earlier members have filesize 0).
    Returns (entries, group_data) where group_data maps group_id -> (data_offset, filesize).
    """
    entries: list[CpioEntry] = []
    pending_groups: dict[tuple[int, int, int], list[CpioEntry]] = {}
    group_data: dict[int, tuple[int, int]] = {}

    while True:
        hdr = fp.read(110)
        if not hdr:
            break
        if len(hdr) < 110:
            raise ValueError("Truncated cpio newc header")
        magic = hdr[:6]
        if magic not in (b"070701", b"070702"):
            raise ValueError(f"Unsupported cpio magic: {magic!r}")

        ino = int(hdr[6:14], 16)
        mode = int(hdr[14:22], 16)
        uid = int(hdr[22:30], 16)
        gid = int(hdr[30:38], 16)
        nlink = int(hdr[38:46], 16)
        mtime = int(hdr[46:54], 16)
        filesize = int(hdr[54:62], 16)
        devmajor = int(hdr[62:70], 16)
        devminor = int(hdr[70:78], 16)
        rdevmajor = int(hdr[78:86], 16)
        rdevminor = int(hdr[86:94], 16)
        namesize = int(hdr[94:102], 16)

        if namesize == 0:
            raise ValueError("Invalid cpio newc entry with namesize 0")

        name_bytes = fp.read(namesize)
        if len(name_bytes) < namesize:
            raise ValueError("Truncated cpio newc filename")
        name = name_bytes.rstrip(b"\x00").decode("utf-8", errors="surrogateescape")

        name_pad = (4 - ((110 + namesize) % 4)) % 4
        if name_pad:
            fp.seek(name_pad, os.SEEK_CUR)

        data_offset = fp.tell()

        if name == "TRAILER!!!":
            # Close any incomplete groups at package boundary (e.g. concatenated newc streams).
            _flush_pending_groups(pending_groups, group_data)
            # Skip NUL padding between concatenated cpio archives if another stream follows.
            while True:
                b = fp.read(1)
                if not b:
                    return entries, group_data
                if b != b"\x00":
                    fp.seek(-1, os.SEEK_CUR)
                    break
            continue

        linkname = ""
        if stat.S_ISLNK(mode):
            link_bytes = fp.read(filesize)
            if len(link_bytes) < filesize:
                raise ValueError(f"Truncated cpio newc symlink target for '{name}'")
            linkname = link_bytes.decode("utf-8", errors="surrogateescape")
        elif filesize:
            fp.seek(filesize, os.SEEK_CUR)

        data_pad = (4 - (filesize % 4)) % 4
        if data_pad:
            fp.seek(data_pad, os.SEEK_CUR)

        entry = CpioEntry(
            idx=len(entries),
            name=name,
            mode=mode,
            uid=uid,
            gid=gid,
            nlink=nlink,
            mtime=mtime,
            filesize=filesize,
            devmajor=devmajor,
            devminor=devminor,
            rdevmajor=rdevmajor,
            rdevminor=rdevminor,
            ino=ino,
            data_offset=data_offset,
            linkname=linkname,
        )
        entries.append(entry)

        if stat.S_ISREG(mode) and nlink > 1:
            key = (devmajor, devminor, ino)
            group = pending_groups.setdefault(key, [])
            group.append(entry)
            # In newc, the last member carries the data (filesize > 0), or for a
            # 0-byte hard-linked file, all nlink members have arrived.
            if filesize > 0 or len(group) == nlink:
                gid_key = group[0].idx
                for member in group:
                    member.group_id = gid_key
                group_data[gid_key] = (data_offset, filesize)
                del pending_groups[key]

    _flush_pending_groups(pending_groups, group_data)
    return entries, group_data


def dedup_newc(input_path: str, output_path: str, allowed_langs: set[str] | None) -> None:
    """Converts a cpio newc archive into a deduplicated uncompressed pax tar archive."""
    with open(input_path, "rb") as src_fp:
        entries, group_data = read_newc_entries(src_fp)

        raw_symlinks: dict[str, str] = dict(USR_MERGE_DIRS)
        for entry in entries:
            if stat.S_ISLNK(entry.mode):
                name = normalize_entry_name(entry.name)
                if name:
                    raw_symlinks[name] = entry.linkname
        symlinks = canonicalize_symlinks(raw_symlinks)

        last_file_idx: dict[str, int] = {}
        canon_names: list[str] = []
        keep_locale: list[bool] = []
        for entry in entries:
            is_dir = stat.S_ISDIR(entry.mode)
            is_sym = stat.S_ISLNK(entry.mode)
            canon = resolve_canonical_name(entry.name, is_dir, is_sym, symlinks)
            canon_names.append(canon)
            keep = should_keep_locale(canon, allowed_langs)
            keep_locale.append(keep)
            if keep and not is_dir:
                last_file_idx[canon] = entry.idx

        seen_entries: dict[str, str] = {}
        seen_parent_dirs: set[str] = set()
        # Maps group_id -> canonical path of the first surviving member (which gets the data).
        group_target: dict[int, str] = {}

        with tarfile.open(output_path, mode="w:") as dst:
            for entry, canon, keep in zip(entries, canon_names, keep_locale):
                if not keep:
                    continue

                if not canon or canon == ".":
                    if "." in seen_entries:
                        continue
                    seen_entries["."] = "dir"
                    ti = tarfile.TarInfo(name=".")
                    ti.type = tarfile.DIRTYPE
                    ti.mode = entry.mode & 0o7777
                    ti.uid = entry.uid
                    ti.gid = entry.gid
                    ti.mtime = entry.mtime
                    dst.addfile(ti)
                    continue

                is_dir = stat.S_ISDIR(entry.mode)
                curr_type = "dir" if is_dir else "file"

                if curr_type == "file" and last_file_idx.get(canon) != entry.idx:
                    continue

                if not register_entry(canon, curr_type, seen_entries, seen_parent_dirs):
                    continue

                ti = tarfile.TarInfo(name=canon)
                ti.mode = entry.mode & 0o7777
                ti.uid = entry.uid
                ti.gid = entry.gid
                ti.mtime = entry.mtime

                if is_dir:
                    ti.type = tarfile.DIRTYPE
                    dst.addfile(ti)
                elif stat.S_ISLNK(entry.mode):
                    ti.type = tarfile.SYMTYPE
                    ti.linkname = entry.linkname
                    dst.addfile(ti)
                elif stat.S_ISCHR(entry.mode):
                    ti.type = tarfile.CHRTYPE
                    ti.devmajor = entry.rdevmajor
                    ti.devminor = entry.rdevminor
                    dst.addfile(ti)
                elif stat.S_ISBLK(entry.mode):
                    ti.type = tarfile.BLKTYPE
                    ti.devmajor = entry.rdevmajor
                    ti.devminor = entry.rdevminor
                    dst.addfile(ti)
                elif stat.S_ISFIFO(entry.mode):
                    ti.type = tarfile.FIFOTYPE
                    dst.addfile(ti)
                elif stat.S_ISREG(entry.mode):
                    if entry.group_id is not None:
                        if entry.group_id not in group_target:
                            # First surviving member of the hard-link group gets the regular file + data.
                            group_target[entry.group_id] = canon
                            data_offset, filesize = group_data[entry.group_id]
                            ti.type = tarfile.REGTYPE
                            ti.size = filesize
                            src_fp.seek(data_offset)
                            dst.addfile(ti, fileobj=src_fp)
                        else:
                            # Subsequent members become hard links to the first surviving member.
                            ti.type = tarfile.LNKTYPE
                            ti.linkname = group_target[entry.group_id]
                            ti.size = 0
                            dst.addfile(ti)
                    else:
                        ti.type = tarfile.REGTYPE
                        ti.size = entry.filesize
                        src_fp.seek(entry.data_offset)
                        dst.addfile(ti, fileobj=src_fp)


def dedup_tar(input_path: str, output_path: str, allowed_langs: set[str] | None) -> None:
    """Deduplicates entries in an uncompressed tar archive."""
    with tarfile.open(input_path, mode="r:") as src:
        symlinks = build_symlink_map(src)

    last_file_idx: dict[str, int] = {}
    with tarfile.open(input_path, mode="r:") as src:
        for idx, member in enumerate(src):
            canon = get_canonical_name(member, symlinks)
            if not should_keep_locale(canon, allowed_langs):
                continue
            if not member.isdir():
                last_file_idx[canon] = idx

    seen_entries: dict[str, str] = {}
    seen_parent_dirs: set[str] = set()

    with tarfile.open(input_path, mode="r:") as src, \
         tarfile.open(output_path, mode="w:") as dst:
        for idx, member in enumerate(src):
            canon = get_canonical_name(member, symlinks)

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

            # Preserving the last occurrence of each file to match package installation ordering:
            # If this is not the last occurrence of this file/symlink in the archive, skip it.
            if curr_type == "file" and last_file_idx.get(canon) != idx:
                continue

            if not register_entry(canon, curr_type, seen_entries, seen_parent_dirs):
                continue

            member.name = canon

            if member.islnk():
                link_norm = normalize_entry_name(member.linkname)
                if link_norm in USR_MERGE_DIRS:
                    member.linkname = USR_MERGE_DIRS[link_norm]
                else:
                    member.linkname = canonicalize_path(link_norm, symlinks)

            if member.isreg():
                with src.extractfile(member) as f:
                    dst.addfile(member, fileobj=f)
            else:
                dst.addfile(member)


def is_newc_archive(path: str) -> bool:
    """Returns True if the file starts with a cpio newc magic header (070701 or 070702)."""
    with open(path, "rb") as fp:
        return fp.read(6) in (b"070701", b"070702")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate entries in a tar or cpio newc archive.")
    parser.add_argument("--input", required=True, help="Path to input uncompressed tar or cpio newc archive")
    parser.add_argument("--output", required=True, help="Path to output deduplicated tar archive")
    parser.add_argument(
        "--install-langs",
        default="",
        help="Language locales to keep (e.g. 'en_US.UTF-8'), filtering non-matching locale files",
    )
    args = parser.parse_args()

    allowed_langs = parse_install_langs(args.install_langs)

    try:
        if is_newc_archive(args.input):
            dedup_newc(args.input, args.output, allowed_langs)
        else:
            dedup_tar(args.input, args.output, allowed_langs)
        return 0

    except Exception as e:
        if os.path.exists(args.output):
            try:
                os.remove(args.output)
            except OSError:
                pass
        sys.stderr.write(f"Error deduplicating archive: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
