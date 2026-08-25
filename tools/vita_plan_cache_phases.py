#!/usr/bin/env python3
"""Plan deterministic warmup phases from a Vita texture-pair manifest.

This is a host-side planning tool. It does not build, deploy, contact the Vita,
or modify the release manifest unless --write-dir is supplied.

The goal is to keep the full generated texture-pair manifest as the source of
truth while allowing a hardware-constrained port to split warmup by scene phase
instead of hand-editing a smaller list.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path

DEFAULT_PHASE_ORDER = (
    "startup",
    "menu",
    "race-common",
    "post-race",
    "karts",
    "course",
    "other",
)

KART_FRAME_RE = re.compile(r"/[^/]+_frame(?P<frame>\d{3})_wheel(?P<wheel>\d+)$")


Pair = tuple[str, str, int]


def parse_manifest(path: Path) -> list[Pair]:
    pairs: list[Pair] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        palette_index = int(fields[2], 0) if len(fields) > 2 else 0
        pairs.append((fields[0], fields[1], palette_index & 0xF))
    return pairs


def phase_for_pair(texture: str, palette: str) -> str:
    paths = (texture, palette)

    if any(path.startswith("textures/startup_logo/") for path in paths):
        return "startup"
    if any(path.startswith("textures/player_selection/") for path in paths):
        return "menu"
    if any(path.startswith("textures/ceremony_data/") for path in paths):
        return "post-race"
    if any(path.startswith("textures/karts/") for path in paths):
        return "karts"
    if any(path.startswith("textures/course") or "/courses/" in path or path.startswith("courses/") for path in paths):
        return "course"
    if any(path.startswith("textures/common_data/") or path.startswith("textures/boo_frames/") for path in paths):
        return "race-common"
    return "other"


def pair_sort_key(pair: Pair) -> tuple[int, int, str, int, str]:
    texture, _palette, _palette_index = pair
    match = KART_FRAME_RE.search(texture)
    if match is not None:
        return (0, int(match.group("frame")), texture, int(match.group("wheel")), texture)
    return (1, 0, texture, 0, texture)


def group_pairs(pairs: list[Pair], phase_order: tuple[str, ...]) -> OrderedDict[str, list[Pair]]:
    grouped: OrderedDict[str, list[Pair]] = OrderedDict((phase, []) for phase in phase_order)
    for pair in pairs:
        phase = phase_for_pair(pair[0], pair[1])
        grouped.setdefault(phase, []).append(pair)

    for phase in list(grouped):
        grouped[phase] = sorted(grouped[phase], key=pair_sort_key)

    return grouped


def parse_limit(raw: str) -> tuple[str, int]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected PHASE=COUNT")
    phase, value = raw.split("=", 1)
    phase = phase.strip()
    if not phase:
        raise argparse.ArgumentTypeError("phase name cannot be empty")
    try:
        limit = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid limit {value!r}") from exc
    if limit < 0:
        raise argparse.ArgumentTypeError("limit must be nonnegative")
    return phase, limit


def apply_limits(grouped: OrderedDict[str, list[Pair]], limits: dict[str, int]) -> OrderedDict[str, list[Pair]]:
    if not limits:
        return grouped
    limited: OrderedDict[str, list[Pair]] = OrderedDict()
    for phase, pairs in grouped.items():
        limit = limits.get(phase)
        limited[phase] = pairs if limit is None or limit == 0 else pairs[:limit]
    return limited


def write_manifest(path: Path, phase: str, pairs: list[Pair]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# Vita Kart 64 CI/TLUT warmup phase: {phase}\n")
        fh.write("# format: <texture_path> <palette_path> <palette_index>\n")
        for texture, palette, palette_index in pairs:
            fh.write(f"{texture} {palette} {palette_index}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=Path("assets/vita/texture-pairs.manifest"))
    parser.add_argument("--write-dir", type=Path, help="optional directory for per-phase manifest files")
    parser.add_argument("--json-output", type=Path, help="optional JSON summary path")
    parser.add_argument(
        "--phase-order",
        default=",".join(DEFAULT_PHASE_ORDER),
        help="comma-separated phase order for reports and optional output",
    )
    parser.add_argument(
        "--limit",
        action="append",
        type=parse_limit,
        default=[],
        metavar="PHASE=COUNT",
        help="optional per-phase cap; COUNT=0 means unlimited",
    )
    args = parser.parse_args()

    phase_order = tuple(phase.strip() for phase in args.phase_order.split(",") if phase.strip())
    if not phase_order:
        parser.error("--phase-order must contain at least one phase")

    pairs = parse_manifest(args.manifest)
    grouped = group_pairs(pairs, phase_order)
    limited = apply_limits(grouped, dict(args.limit))

    summary = {
        "manifest": str(args.manifest),
        "input_pairs": len(pairs),
        "output_pairs": sum(len(items) for items in limited.values()),
        "phases": [
            {
                "phase": phase,
                "input_pairs": len(grouped.get(phase, [])),
                "output_pairs": len(limited.get(phase, [])),
            }
            for phase in limited
        ],
    }

    if args.write_dir is not None:
        for phase, phase_pairs in limited.items():
            if not phase_pairs:
                continue
            write_manifest(args.write_dir / f"texture-pairs-{phase}.manifest", phase, phase_pairs)
        summary["write_dir"] = str(args.write_dir)

    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
