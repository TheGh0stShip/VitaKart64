#!/usr/bin/env python3
"""Merge Vita texture miss logs into a CI/TLUT warmup overlay manifest.

Input lines are produced by diagnostic builds compiled with
VITAKART_TEXTURE_MISS_LOG. The tool preserves existing manifest pairs and adds
new pairs only when both the texture resource and a palette resource are known.
"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path


def load_manifest(path: Path) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    if not path.exists():
        return pairs

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        palette_index = int(fields[2], 0) if len(fields) > 2 else 0
        pairs.append((fields[0], fields[1], palette_index & 0xF))
    return pairs


def parse_log_line(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in shlex.split(raw, comments=False, posix=True):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        result[key] = value
    return result


def pairs_from_log(path: Path) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    if not path.exists():
        return pairs

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = parse_log_line(raw)
        texture = fields.get("resource", "")
        palette = fields.get("palette_resource0", "") or fields.get("palette_resource1", "")
        if not texture or not palette or texture == "<raw>":
            continue
        try:
            palette_index = int(fields.get("palette", "0"), 0) & 0xF
        except ValueError:
            palette_index = 0
        pairs.append((texture, palette, palette_index))
    return pairs


def write_manifest(path: Path, pairs: list[tuple[str, str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    unique: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        unique.append(pair)

    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Vita Kart 64 CI/TLUT texture warmup overlay\n")
        fh.write("# format: <texture_path> <palette_path> <palette_index>\n")
        fh.write("# Hardware-discovered pairs belong here. Makefile merges this overlay into\n")
        fh.write("# assets/vita/texture-pairs.manifest so generator refreshes do not erase\n")
        fh.write("# supervised runtime discoveries.\n")
        for texture, palette, palette_index in unique:
            fh.write(f"{texture} {palette} {palette_index}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="texture-misses.log copied from ux0:data/vitakart64")
    parser.add_argument("manifest", nargs="?", type=Path, default=Path("assets/vita/texture-pairs-extra.manifest"))
    args = parser.parse_args()

    existing = load_manifest(args.manifest)
    discovered = pairs_from_log(args.log)
    write_manifest(args.manifest, existing + discovered)
    print(f"merged {len(discovered)} discovered pairs into {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
