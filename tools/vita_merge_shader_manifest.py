#!/usr/bin/env python3
"""Merge observed Vita shader manifests into the packaged shader seed."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

LINE_RE = re.compile(r"^\s*([0-9a-fA-F]+)\s+([0-9a-fA-F]+)")


def load_pairs(path: Path) -> list[tuple[int, int]]:
    if not path.exists():
        return []

    pairs: list[tuple[int, int]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0]
        match = LINE_RE.match(line)
        if match is None:
            continue
        pairs.append((int(match.group(1), 16), int(match.group(2), 16)))
    return pairs


def write_pairs(path: Path, pairs: list[tuple[int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[int, int]] = set()
    ordered: list[tuple[int, int]] = []
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        ordered.append(pair)

    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for id0, id1 in ordered:
            fh.write(f"{id0:016x} {id1:016x}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observed", type=Path, help="shader-manifest.txt copied from ux0:data/vitakart64")
    parser.add_argument("seed", nargs="?", type=Path, default=Path("assets/vita/shader-manifest.txt"))
    args = parser.parse_args()

    seed_pairs = load_pairs(args.seed)
    observed_pairs = load_pairs(args.observed)
    write_pairs(args.seed, seed_pairs + observed_pairs)
    print(f"merged {len(observed_pairs)} observed shader pairs into {args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
