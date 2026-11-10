#!/usr/bin/env python3
"""Deduplicates directory and file entries in an uncompressed tar archive and filters locales."""

import argparse
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

    seen_dirs = set()
    seen_files = set()

    with tarfile.open(args.input, mode="r:") as src, \
         tarfile.open(args.output, mode="w:") as dst:
        for member in src:
            norm = normalize_entry_name(member.name)

            if not should_keep_locale(norm, allowed_langs):
                continue

            if not norm or norm == ".":
                if "." in seen_dirs:
                    continue
                seen_dirs.add(".")
                member.name = "."
                dst.addfile(member)
                continue

            if member.isdir():
                if norm in seen_dirs:
                    continue
                seen_dirs.add(norm)
                member.name = norm
                dst.addfile(member)
            else:
                if norm in seen_files:
                    continue
                seen_files.add(norm)
                member.name = norm
                if member.islnk() and member.linkname.startswith("./"):
                    member.linkname = normalize_entry_name(member.linkname)

                if member.isreg():
                    with src.extractfile(member) as f:
                        dst.addfile(member, fileobj=f)
                else:
                    dst.addfile(member)

    return 0


if __name__ == "__main__":
    sys.exit(main())
