#!/usr/bin/env python3
"""Safely inspect, extract, repack, and verify employee archive ZIP packages."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import unicodedata
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

MAX_ENTRIES = 5000
MAX_FILE_SIZE = 512 * 1024 * 1024
MAX_TOTAL_SIZE = 4 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250


def cjk_score(value):
    return sum("\u3400" <= char <= "\u9fff" for char in value)


def decoded_name(info):
    value = info.filename
    if info.flag_bits & 0x800:
        return unicodedata.normalize("NFC", value)
    try:
        raw = value.encode("cp437")
    except UnicodeEncodeError:
        return unicodedata.normalize("NFC", value)
    candidates = [value]
    for encoding in ("gb18030", "utf-8"):
        try:
            candidates.append(raw.decode(encoding))
        except UnicodeDecodeError:
            pass
    best = max(candidates, key=lambda item: (cjk_score(item), -sum(ord(ch) < 32 for ch in item)))
    return unicodedata.normalize("NFC", best)


def safe_relative_path(value):
    normalized = unicodedata.normalize("NFC", str(value or "")).replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"unsafe archive path: {value!r}")
    parts = []
    for part in PurePosixPath(normalized).parts:
        if part in {"", "."}:
            continue
        if part == ".." or "\x00" in part or any(ord(char) < 32 for char in part):
            raise ValueError(f"unsafe archive path: {value!r}")
        parts.append(part)
    if not parts:
        raise ValueError(f"empty archive path: {value!r}")
    return PurePosixPath(*parts)


def is_symlink(info):
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def sha256_stream(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def archive_index(archive_path, include_hashes=False):
    archive_path = Path(archive_path)
    entries = []
    seen = set()
    total_size = 0
    with ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ValueError(f"archive has too many entries: {len(infos)} > {MAX_ENTRIES}")
        for info in infos:
            relative = safe_relative_path(decoded_name(info))
            key = relative.as_posix()
            if key in seen:
                raise ValueError(f"duplicate path after filename decoding: {key}")
            seen.add(key)
            if is_symlink(info):
                raise ValueError(f"symbolic link is not allowed: {key}")
            if info.file_size > MAX_FILE_SIZE:
                raise ValueError(f"archive member is too large: {key}")
            total_size += info.file_size
            if total_size > MAX_TOTAL_SIZE:
                raise ValueError("archive uncompressed size exceeds the safety limit")
            if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise ValueError(f"suspicious compression ratio: {key}")
            item = {
                "path": key,
                "directory": info.is_dir(),
                "size": info.file_size,
                "compressed_size": info.compress_size,
                "crc": f"{info.CRC:08x}",
                "passive_only": relative.suffix.lower() in {".lnk", ".url", ".webloc"},
            }
            if include_hashes and not info.is_dir():
                with archive.open(info) as source:
                    item["sha256"] = sha256_stream(source)
            entries.append(item)
    return {
        "archive": archive_path.name,
        "entry_count": len(entries),
        "file_count": sum(not item["directory"] for item in entries),
        "total_uncompressed_size": total_size,
        "entries": entries,
    }


def write_json(data, target):
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if target:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def extract_archive(archive_path, destination, manifest_path=None):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    manifest = archive_index(archive_path, include_hashes=True)
    by_path = {item["path"]: item for item in manifest["entries"]}
    with ZipFile(archive_path) as archive:
        for info in archive.infolist():
            relative = safe_relative_path(decoded_name(info))
            target = (destination / Path(*relative.parts)).resolve()
            if destination != target and destination not in target.parents:
                raise ValueError(f"archive path escapes destination: {relative}")
            item = by_path[relative.as_posix()]
            if item["directory"]:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            os.chmod(target, 0o600)
    if manifest_path:
        write_json(manifest, manifest_path)
    return manifest


def pack_directory(source_dir, output_path):
    source_dir = Path(source_dir).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if source_dir == output_path or source_dir in output_path.parents:
        raise ValueError("output ZIP cannot be placed inside the source tree")
    paths = sorted(source_dir.rglob("*"), key=lambda item: item.relative_to(source_dir).as_posix())
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            if path.is_symlink():
                raise ValueError(f"symbolic link is not allowed: {path}")
            relative = path.relative_to(source_dir).as_posix()
            if path.is_dir():
                if not any(path.iterdir()):
                    info = ZipInfo(relative.rstrip("/") + "/")
                    info.external_attr = (stat.S_IFDIR | 0o700) << 16
                    archive.writestr(info, b"")
                continue
            archive.write(path, relative)
    return archive_index(output_path, include_hashes=True)


def verify_archives(original_path, revised_path):
    original = archive_index(original_path, include_hashes=True)
    revised = archive_index(revised_path, include_hashes=True)
    original_files = {item["path"]: item for item in original["entries"] if not item["directory"]}
    revised_files = {item["path"]: item for item in revised["entries"] if not item["directory"]}
    missing = sorted(set(original_files) - set(revised_files))
    added = sorted(set(revised_files) - set(original_files))
    changed = sorted(
        path for path in set(original_files) & set(revised_files)
        if original_files[path].get("sha256") != revised_files[path].get("sha256")
    )
    unchanged = len(original_files) - len(missing) - len(changed)
    return {
        "valid": not missing,
        "original_file_count": len(original_files),
        "revised_file_count": len(revised_files),
        "unchanged_file_count": unchanged,
        "changed_paths": changed,
        "added_paths": added,
        "missing_paths": missing,
    }


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("archive")
    inspect_parser.add_argument("--manifest")

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("archive")
    extract_parser.add_argument("destination")
    extract_parser.add_argument("--manifest")

    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("source")
    pack_parser.add_argument("output")
    pack_parser.add_argument("--manifest")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("original")
    verify_parser.add_argument("revised")
    verify_parser.add_argument("--report")

    args = parser.parse_args()
    try:
        if args.command == "inspect":
            write_json(archive_index(args.archive, include_hashes=False), args.manifest)
        elif args.command == "extract":
            manifest = extract_archive(args.archive, args.destination, args.manifest)
            if not args.manifest:
                write_json(manifest, None)
        elif args.command == "pack":
            write_json(pack_directory(args.source, args.output), args.manifest)
        else:
            report = verify_archives(args.original, args.revised)
            write_json(report, args.report)
            if not report["valid"]:
                raise SystemExit(2)
    except (BadZipFile, OSError, ValueError) as error:
        sys.stderr.write(f"archive package error: {error}\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
