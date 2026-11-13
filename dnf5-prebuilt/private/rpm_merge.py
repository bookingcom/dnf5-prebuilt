#!/usr/bin/env python3
"""Merges RPM package payloads into a single cpio newc archive with globally unique inodes."""

import argparse
import os
import shutil
import subprocess
import sys

NEWC_TRAILER = b"TRAILER!!!"


def _write_trailer(out_fp) -> None:
    """Writes a cpio newc TRAILER!!! entry."""
    name_bytes = NEWC_TRAILER + b"\x00"
    hdr = (
        f"070701{0:08x}{0:08x}{0:08x}{0:08x}"
        f"{1:08x}{0:08x}{0:08x}"
        f"{0:08x}{0:08x}{0:08x}{0:08x}"
        f"{len(name_bytes):08x}{0:08x}"
    ).encode("ascii")
    out_fp.write(hdr)
    out_fp.write(name_bytes)
    pad = (4 - ((110 + len(name_bytes)) % 4)) % 4
    if pad:
        out_fp.write(b"\x00" * pad)


def _read_exact(fp, size: int) -> bytes:
    """Reads exactly size bytes from fp, raising ValueError on premature EOF."""
    buf = fp.read(size)
    if len(buf) < size:
        raise ValueError(f"Unexpected EOF in cpio newc stream (expected {size} bytes, got {len(buf)})")
    return buf


def _copy_exact(src_fp, dst_fp, size: int, chunk_size: int = 65536) -> None:
    """Copies exactly size bytes from src_fp to dst_fp."""
    remaining = size
    while remaining > 0:
        chunk = src_fp.read(min(remaining, chunk_size))
        if not chunk:
            raise ValueError(f"Unexpected EOF copying {size} bytes ({remaining} remaining)")
        dst_fp.write(chunk)
        remaining -= len(chunk)


def merge_rpm_newc(
    bsdtar: str,
    rpm_path: str,
    exclude_patterns: list[str],
    out_fp,
    next_ino: int,
) -> int:
    """Extracts a single RPM payload as cpio newc, remapping inodes to be globally unique."""
    cmd = [
        bsdtar,
        "-cf",
        "-",
        "--format=newc",
        "--numeric-owner",
        "--owner=0",
        "--group=0",
    ]
    for pattern in exclude_patterns:
        cmd.append(f"--exclude={pattern}")
    cmd.append(f"@{rpm_path}")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    assert proc.stderr is not None

    ino_map: dict[tuple[int, int, int], int] = {}

    try:
        while True:
            hdr = proc.stdout.read(110)
            if not hdr:
                break
            if len(hdr) < 110:
                raise ValueError(f"Truncated cpio newc header in {rpm_path}")

            magic = hdr[:6]
            if magic not in (b"070701", b"070702"):
                raise ValueError(f"Unsupported cpio magic {magic!r} in {rpm_path}")

            ino = int(hdr[6:14], 16)
            filesize = int(hdr[54:62], 16)
            devmajor = int(hdr[62:70], 16)
            devminor = int(hdr[70:78], 16)
            namesize = int(hdr[94:102], 16)
            if namesize == 0:
                raise ValueError(f"Invalid cpio newc entry with namesize 0 in {rpm_path}")

            name_bytes = _read_exact(proc.stdout, namesize)
            name_pad = (4 - ((110 + namesize) % 4)) % 4
            pad_bytes = _read_exact(proc.stdout, name_pad) if name_pad else b""

            if name_bytes.rstrip(b"\x00") == NEWC_TRAILER:
                # Drain any trailing padding/bytes and stop before writing TRAILER!!!.
                with open(os.devnull, "wb") as devnull:
                    shutil.copyfileobj(proc.stdout, devnull)
                break

            key = (devmajor, devminor, ino)
            mapped_ino = ino_map.get(key)
            if mapped_ino is None:
                mapped_ino = next_ino
                next_ino += 1
                ino_map[key] = mapped_ino

            # Rewrite c_ino and normalize devmajor/devminor to 0 so keys are globally unique.
            patched_hdr = (
                b"070701"
                + f"{mapped_ino:08x}".encode("ascii")
                + hdr[14:62]
                + b"0000000000000000"
                + hdr[78:102]
                + b"00000000"
            )
            out_fp.write(patched_hdr)
            out_fp.write(name_bytes)
            if pad_bytes:
                out_fp.write(pad_bytes)

            data_pad = (4 - (filesize % 4)) % 4
            _copy_exact(proc.stdout, out_fp, filesize + data_pad)
    finally:
        proc.stdout.close()
        stderr_data = proc.stderr.read().decode("utf-8", errors="replace")
        proc.stderr.close()
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"bsdtar failed on {rpm_path} (exit {rc}): {stderr_data.strip()}")

    return next_ino


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge RPM payloads into a cpio newc archive.")
    parser.add_argument("--bsdtar", required=True, help="Path to bsdtar binary")
    parser.add_argument("--output", required=True, help="Path to output cpio newc archive")
    parser.add_argument("--exclude", action="append", default=[], help="Glob pattern to exclude")
    parser.add_argument("--rpm", action="append", default=[], help="Input RPM package path")
    args = parser.parse_args()

    try:
        next_ino = 1
        with open(args.output, "wb") as out_fp:
            for rpm_path in args.rpm:
                next_ino = merge_rpm_newc(args.bsdtar, rpm_path, args.exclude, out_fp, next_ino)
            _write_trailer(out_fp)
        return 0
    except Exception as e:
        if os.path.exists(args.output):
            try:
                os.remove(args.output)
            except OSError:
                pass
        sys.stderr.write(f"Error merging RPMs: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
