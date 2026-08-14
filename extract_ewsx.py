#!/usr/bin/env python3
"""Inspect and extract EasyWorship ``.ewsx`` schedule archives.

An ``.ewsx`` file is a ZIP archive containing the schedule database and its
associated media. By default, this tool extracts the archive beside the input
file into a directory named ``<archive-stem>_extracted``. Windows-style
backslashes in archive member names are converted to normal directory
separators, so an entry such as ``media\\slide.jpg`` becomes
``media/slide.jpg`` on macOS and Linux.

Examples:

    # Extract a schedule beside the source archive.
    uv run extract_ewsx.py /path/to/02082026.ewsx

    # Inspect every entry without creating or changing files.
    uv run extract_ewsx.py /path/to/02082026.ewsx --dry-run

The dry run reports each member's stored size, compressed size, compression
ratio, and CRC. During extraction, unsafe paths are rejected. Some EasyWorship
archives contain incorrect CRC values in their ZIP metadata; in that case the
tool preserves the decompressed bytes and prints a warning for each mismatch.
"""

from __future__ import annotations

import argparse
import binascii
import os
import sys
import zipfile
from pathlib import Path, PurePosixPath


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Inspect or extract an EasyWorship .ewsx schedule archive."
    )
    parser.add_argument("archive", type=Path, help="Path to the .ewsx file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List every archive entry and its details without extracting",
    )
    return parser.parse_args()


def format_size(size: int) -> str:
    """Return a human-readable byte size."""
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def normalise_member_name(name: str) -> PurePosixPath:
    """Convert Windows separators and reject paths that escape extraction root."""
    parts = [part for part in name.replace("\\", "/").split("/") if part not in ("", ".")]
    path = PurePosixPath(*parts)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive path: {name!r}")
    return path


def show_contents(archive: Path) -> None:
    """Print complete metadata for every archive member."""
    with zipfile.ZipFile(archive) as zip_file:
        infos = zip_file.infolist()
        print(f"Archive: {archive}")
        print(f"Entries: {len(infos)}")
        for info in infos:
            kind = "directory" if info.is_dir() else "file"
            ratio = (
                info.compress_size / info.file_size * 100
                if info.file_size
                else 0
            )
            print(
                f"{kind}: {info.filename} | "
                f"size={format_size(info.file_size)} | "
                f"compressed={format_size(info.compress_size)} | "
                f"ratio={ratio:.1f}% | CRC={info.CRC:#010x}"
            )


def extract_archive(archive: Path) -> Path:
    """Extract an archive beside itself into a ``*_extracted`` directory."""
    destination = archive.parent / f"{archive.stem}_extracted"
    destination.mkdir(exist_ok=True)

    with zipfile.ZipFile(archive) as zip_file:
        infos = [(info, normalise_member_name(info.filename)) for info in zip_file.infolist()]
        directory_members = {
            member
            for _, member in infos
            if any(other != member and member in other.parents for _, other in infos)
        }
        for info, member in infos:
            target = destination.joinpath(*member.parts)
            target_root = destination.resolve()
            if os.path.commonpath((str(target_root), str(target.resolve()))) != str(
                target_root
            ):
                raise ValueError(f"Unsafe archive path: {info.filename!r}")
            if info.is_dir() or member in directory_members:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            actual_crc = 0
            with zip_file.open(info) as source, target.open("wb") as output:
                # Some EasyWorship archives have incorrect CRC values in their
                # ZIP metadata. Keep the bytes, but validate and report them.
                source._expected_crc = None  # type: ignore[attr-defined]
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    actual_crc = binascii.crc32(chunk, actual_crc)
            actual_crc &= 0xFFFFFFFF
            if actual_crc != info.CRC:
                print(
                    f"Warning: CRC mismatch for {info.filename} "
                    f"(archive={info.CRC:#010x}, actual={actual_crc:#010x})",
                    file=sys.stderr,
                )

    return destination


def main() -> int:
    """Run the command-line tool."""
    args = parse_args()
    archive = args.archive.expanduser().resolve()
    if not archive.is_file():
        print(f"Error: file not found: {archive}", file=sys.stderr)
        return 2
    if not zipfile.is_zipfile(archive):
        print(f"Error: not a valid ZIP/.ewsx archive: {archive}", file=sys.stderr)
        return 2

    try:
        if args.dry_run:
            show_contents(archive)
        else:
            destination = extract_archive(archive)
            print(f"Extracted {archive.name} to {destination}")
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
