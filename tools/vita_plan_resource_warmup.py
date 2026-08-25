#!/usr/bin/env python3
"""Plan Vita Kart 64 resource warmup coverage from an O2R/OTR archive.

This host-side tool is read-only unless --write-dir is supplied. It does not
build, deploy, launch, contact the Vita, or modify the release package.

The intent is to make non-texture first-use work visible. Texture/TLUT coverage
has dedicated tooling; this script classifies audio, model, texture, and misc
resources by rough scene phase so remaining stutter can be separated into cache
coverage, archive I/O, audio setup, or scene-specific runtime work.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, OrderedDict
from pathlib import Path
from zipfile import ZipFile

DEFAULT_PHASE_ORDER = (
    "startup",
    "menu",
    "race-common",
    "karts",
    "tracks",
    "post-race",
    "audio",
    "other",
)


def resource_kind(path: str) -> str:
    if path.startswith("sound/"):
        return "audio"
    if path.startswith("textures/"):
        return "texture"
    if path.startswith("models/"):
        return "model"
    if path.startswith("courses/"):
        return "course"
    if path.startswith("other/"):
        return "other-data"
    return "misc"


def phase_for_path(path: str) -> str:
    if path.startswith(("textures/startup_logo/", "models/startup_logo/", "other/startup_logo/")):
        return "startup"
    if path.startswith("textures/player_selection/"):
        return "menu"
    if path.startswith(("textures/ceremony_data/", "models/ceremony_data/", "other/ceremony_data/")):
        return "post-race"
    if path.startswith("textures/karts/"):
        return "karts"
    if path.startswith(("textures/tracks/", "models/tracks/", "other/tracks/", "courses/")):
        return "tracks"
    if path.startswith("sound/"):
        return "audio"
    if path.startswith(
        (
            "textures/common_data/",
            "textures/boo_frames/",
            "textures/other_textures/",
            "textures/texture_tkmk00/",
            "textures/texture_data_2/",
            "textures/some_data/",
            "models/common_data/",
            "models/data_800E8700/",
            "models/data_segment2/",
            "other/common_data/",
        )
    ):
        return "race-common"
    return "other"


def iter_runtime_resources(archive: Path) -> list[str]:
    with ZipFile(archive, "r") as zf:
        return sorted(
            name
            for name in zf.namelist()
            if name.startswith(("textures/", "models/", "sound/", "other/", "courses/"))
        )


def group_resources(paths: list[str], phase_order: tuple[str, ...]) -> OrderedDict[str, list[str]]:
    grouped: OrderedDict[str, list[str]] = OrderedDict((phase, []) for phase in phase_order)
    for path in paths:
        phase = phase_for_path(path)
        grouped.setdefault(phase, []).append(path)
    return grouped


def write_phase_manifest(path: Path, phase: str, resources: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# Vita Kart 64 resource warmup phase: {phase}\n")
        fh.write("# format: <resource_path>\n")
        for resource in resources:
            fh.write(f"{resource}\n")


def summarize_phase(phase: str, resources: list[str]) -> dict[str, object]:
    kinds = Counter(resource_kind(path) for path in resources)
    return {
        "phase": phase,
        "resources": len(resources),
        "kinds": dict(sorted(kinds.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=Path("mk64-vita.o2r"))
    parser.add_argument("--write-dir", type=Path, help="optional directory for per-phase resource manifests")
    parser.add_argument("--json-output", type=Path, help="optional JSON summary path")
    parser.add_argument(
        "--phase-order",
        default=",".join(DEFAULT_PHASE_ORDER),
        help="comma-separated phase order for reports and optional output",
    )
    args = parser.parse_args()

    phase_order = tuple(phase.strip() for phase in args.phase_order.split(",") if phase.strip())
    if not phase_order:
        parser.error("--phase-order must contain at least one phase")

    resources = iter_runtime_resources(args.archive)
    grouped = group_resources(resources, phase_order)

    if args.write_dir is not None:
        for phase, phase_resources in grouped.items():
            if phase_resources:
                write_phase_manifest(args.write_dir / f"resources-{phase}.manifest", phase, phase_resources)

    summary = {
        "archive": str(args.archive),
        "resources": len(resources),
        "phases": [summarize_phase(phase, phase_resources) for phase, phase_resources in grouped.items()],
    }
    if args.write_dir is not None:
        summary["write_dir"] = str(args.write_dir)

    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
