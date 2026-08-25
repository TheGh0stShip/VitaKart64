#!/usr/bin/env python3
"""Filter or cap a Vita CI/TLUT texture-pair manifest.

This is a supervised fallback tool. The default product target remains full
warmup coverage; use this only if full warmup is too expensive on hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

CRITICAL_DIRS = (
    "textures/common_data/",
    "textures/ceremony_data/",
    "textures/player_selection/",
    "textures/startup_logo/",
)


def load_pairs(path: Path) -> list[tuple[str, str, str]]:
    pairs: list[tuple[str, str, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        pairs.append((fields[0], fields[1], fields[2] if len(fields) > 2 else "0"))
    return pairs


def is_critical(texture: str) -> bool:
    return texture.startswith(CRITICAL_DIRS)


def is_kart(texture: str) -> bool:
    return texture.startswith("textures/karts/")


def select_pairs(pairs: list[tuple[str, str, str]], mode: str, limit: int) -> list[tuple[str, str, str]]:
    if mode == "all":
        selected = pairs
    elif mode == "critical":
        selected = [pair for pair in pairs if is_critical(pair[0])]
    elif mode == "critical-plus-karts":
        selected = [pair for pair in pairs if is_critical(pair[0]) or is_kart(pair[0])]
    elif mode == "karts-only":
        selected = [pair for pair in pairs if is_kart(pair[0])]
    else:
        raise ValueError(f"unsupported mode: {mode}")

    return selected[:limit] if limit > 0 else selected


def write_pairs(path: Path, pairs: list[tuple[str, str, str]], source: Path, mode: str, limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Vita Kart 64 filtered CI/TLUT texture warmup manifest\n")
        fh.write(f"# source: {source}\n")
        fh.write(f"# mode: {mode}\n")
        fh.write(f"# limit: {limit}\n")
        fh.write("# format: <texture_path> <palette_path> <palette_index>\n")
        for texture, palette, palette_index in pairs:
            fh.write(f"{texture} {palette} {palette_index}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=Path("assets/vita/texture-pairs.manifest"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("all", "critical", "critical-plus-karts", "karts-only"), default="critical")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    pairs = load_pairs(args.input)
    selected = select_pairs(pairs, args.mode, args.limit)
    write_pairs(args.output, selected, args.input, args.mode, args.limit)
    print(f"wrote {len(selected)} of {len(pairs)} pairs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
