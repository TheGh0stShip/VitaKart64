#!/usr/bin/env python3
"""Audit Vita Kart 64 O2R/OTR archive layout for startup/runtime hitch risks.

This is a host-side read-only tool. It does not build, deploy, launch, contact
the Vita, or rewrite the archive. It reports whether runtime-critical resources
are stored or compressed, where critical entries appear in archive order, and
which directories dominate compressed runtime payload.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

CRITICAL_PREFIXES = (
    "textures/common_data/",
    "textures/ceremony_data/",
    "textures/player_selection/",
    "textures/startup_logo/",
    "textures/karts/",
    "sound/",
    "models/common_data/",
    "models/ceremony_data/",
    "models/startup_logo/",
    "models/tracks/",
    "other/common_data/",
    "other/ceremony_data/",
    "other/startup_logo/",
)

RUNTIME_PREFIXES = (
    "textures/",
    "models/",
    "sound/",
    "other/",
    "courses/",
)


def directory_name(path: str) -> str:
    return path.rsplit("/", 1)[0] + "/" if "/" in path else "."


def is_runtime(path: str) -> bool:
    return path.startswith(RUNTIME_PREFIXES)


def is_critical(path: str) -> bool:
    return path.startswith(CRITICAL_PREFIXES)


def compression_name(method: int) -> str:
    if method == zipfile.ZIP_STORED:
        return "stored"
    if method == zipfile.ZIP_DEFLATED:
        return "deflated"
    if method == zipfile.ZIP_BZIP2:
        return "bzip2"
    if method == zipfile.ZIP_LZMA:
        return "lzma"
    return f"method_{method}"


def audit_archive(path: Path, late_critical_index: int) -> dict[str, object]:
    with zipfile.ZipFile(path, "r") as zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]

    runtime_infos = [(index, info) for index, info in enumerate(infos) if is_runtime(info.filename)]
    critical_infos = [(index, info) for index, info in runtime_infos if is_critical(info.filename)]
    compressed_runtime = [(index, info) for index, info in runtime_infos if info.compress_type != zipfile.ZIP_STORED]
    compressed_critical = [(index, info) for index, info in critical_infos if info.compress_type != zipfile.ZIP_STORED]
    late_critical = [(index, info) for index, info in critical_infos if index > late_critical_index]

    method_counts = Counter(compression_name(info.compress_type) for _index, info in runtime_infos)
    compressed_by_dir: dict[str, int] = defaultdict(int)
    for _index, info in compressed_runtime:
        compressed_by_dir[directory_name(info.filename)] += info.file_size

    return {
        "archive": str(path),
        "entries": len(infos),
        "runtime_entries": len(runtime_infos),
        "critical_entries": len(critical_infos),
        "runtime_compression_methods": dict(sorted(method_counts.items())),
        "compressed_runtime_entries": len(compressed_runtime),
        "compressed_critical_entries": len(compressed_critical),
        "late_critical_entries": len(late_critical),
        "late_critical_index_threshold": late_critical_index,
        "compressed_runtime_bytes": sum(info.file_size for _index, info in compressed_runtime),
        "compressed_critical_bytes": sum(info.file_size for _index, info in compressed_critical),
        "first_critical_index": min((index for index, _info in critical_infos), default=-1),
        "last_critical_index": max((index for index, _info in critical_infos), default=-1),
        "compressed_runtime_dirs": [
            {"directory": directory, "bytes": byte_count}
            for directory, byte_count in sorted(compressed_by_dir.items(), key=lambda item: (-item[1], item[0]))[:40]
        ],
        "compressed_critical_examples": [
            {
                "index": index,
                "path": info.filename,
                "method": compression_name(info.compress_type),
                "size": info.file_size,
                "compressed_size": info.compress_size,
            }
            for index, info in compressed_critical[:80]
        ],
        "late_critical_examples": [
            {
                "index": index,
                "path": info.filename,
                "method": compression_name(info.compress_type),
                "size": info.file_size,
                "compressed_size": info.compress_size,
            }
            for index, info in late_critical[:80]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=Path("mk64-vita.o2r"))
    parser.add_argument("--json-output", type=Path, help="optional JSON output path")
    parser.add_argument(
        "--late-critical-index",
        type=int,
        default=5000,
        help="critical entries after this archive index are reported as late",
    )
    parser.add_argument("--fail-on-compressed-critical", action="store_true")
    parser.add_argument("--fail-on-late-critical", action="store_true")
    args = parser.parse_args()

    result = audit_archive(args.archive, args.late_critical_index)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)

    if args.fail_on_compressed_critical and result["compressed_critical_entries"]:
        return 1
    if args.fail_on_late_critical and result["late_critical_entries"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
