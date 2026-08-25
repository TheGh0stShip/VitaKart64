#!/usr/bin/env python3
"""Apply a harvested preload-summary.txt to a hardware run report.

This is a host-side reporting helper. It does not build, deploy, launch,
contact the Vita, or validate runtime behavior. It only fills structured
preload counter fields in a local hardware-runs/*.md report.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FIELD_KEYS = {
    "Runtime cache ready line": "runtime_cache_ready_line",
    "Preload ready marker": "preload_ready_marker",
    "Preload skipped": "preload_skipped",
    "Preload skip reason": "preload_skip_reason",
    "Preload ready marker present before run": "preload_ready_marker_present_before_run",
    "Runtime texture pair limit": "texture_pair_limit",
    "Preload resources": "resident_resources",
    "Preload GPU textures": "gpu_textures",
    "Preload CI/TLUT textures": "paletted_gpu_textures",
    "Preload manifest CI/TLUT pairs attempted": "paletted_manifest_pairs_attempted",
    "Preload manifest CI/TLUT pairs warmed": "paletted_manifest_pairs_warmed",
    "Preload manifest CI/TLUT duplicate pairs": "paletted_manifest_pairs_duplicate",
    "Preload heuristic CI/TLUT pairs attempted": "paletted_heuristic_pairs_attempted",
    "Preload heuristic CI/TLUT pairs warmed": "paletted_heuristic_pairs_warmed",
    "Preload heuristic CI/TLUT duplicate pairs": "paletted_heuristic_pairs_duplicate",
    "Preload audio warmup banks": "audio_warmup_banks",
    "Preload audio warmup sequences": "audio_warmup_sequences",
    "Preload TLUT resources": "palette_resources",
    "Preload audio resources": "audio_resources",
    "Preload model resources": "model_resources",
    "Preload other resources": "other_resources",
    "Preload deferred textures": "deferred_textures",
    "Reserved texture slots": "reserved_texture_slots",
    "Preload priority common/menu": "preload_priority_common_menu",
    "Preload priority audio": "preload_priority_audio",
    "Preload priority ceremony/post-race": "preload_priority_ceremony",
    "Preload priority common models/other": "preload_priority_common_models",
    "Preload priority karts": "preload_priority_karts",
    "Preload priority tracks": "preload_priority_tracks",
    "Preload priority other": "preload_priority_other",
    "Preload priority common/menu ms": "preload_priority_common_menu_ms",
    "Preload priority audio ms": "preload_priority_audio_ms",
    "Preload priority ceremony/post-race ms": "preload_priority_ceremony_ms",
    "Preload priority common models/other ms": "preload_priority_common_models_ms",
    "Preload priority karts ms": "preload_priority_karts_ms",
    "Preload priority tracks ms": "preload_priority_tracks_ms",
    "Preload priority other ms": "preload_priority_other_ms",
    "Preload priority common/menu GPU ms": "preload_priority_common_menu_gpu_ms",
    "Preload priority audio GPU ms": "preload_priority_audio_gpu_ms",
    "Preload priority ceremony/post-race GPU ms": "preload_priority_ceremony_gpu_ms",
    "Preload priority common models/other GPU ms": "preload_priority_common_models_gpu_ms",
    "Preload priority karts GPU ms": "preload_priority_karts_gpu_ms",
    "Preload priority tracks GPU ms": "preload_priority_tracks_gpu_ms",
    "Preload priority other GPU ms": "preload_priority_other_gpu_ms",
    "Preload resource phase ms": "resource_phase_ms",
    "Preload CI/TLUT phase ms": "paletted_phase_ms",
    "Preload audio phase ms": "audio_phase_ms",
    "Preload total ms": "total_ms",
}


def load_summary(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def synthesize_ready_line(summary: dict[str, str]) -> str:
    return (
        f"{summary.get('resident_resources', '')} RES   "
        f"{summary.get('gpu_textures', '')} GPU   "
        f"{summary.get('paletted_gpu_textures', '')} CI/TLUT   "
        f"{summary.get('palette_resources', '')} TLUT   "
        f"{summary.get('audio_resources', '')} AUD   "
        f"{summary.get('audio_warmup_banks', '')} BNK   "
        f"{summary.get('audio_warmup_sequences', '')} SEQ   "
        f"{summary.get('model_resources', '')} MDL   "
        f"{summary.get('other_resources', '')} OTHER   "
        f"{summary.get('deferred_textures', '')} DEF"
    ).strip()


def replacement_value(label: str, summary: dict[str, str]) -> str | None:
    key = FIELD_KEYS[label]
    if key == "runtime_cache_ready_line":
        return synthesize_ready_line(summary)
    return summary.get(key)


def apply_summary(report_text: str, summary: dict[str, str]) -> tuple[str, int]:
    replacements = 0
    lines: list[str] = []

    for line in report_text.splitlines():
        replaced = False
        for label in FIELD_KEYS:
            pattern = rf"^(- {re.escape(label)}:\s*).*$"
            match = re.match(pattern, line)
            if match is None:
                continue
            value = replacement_value(label, summary)
            if value is not None:
                lines.append(f"{match.group(1)}{value}")
                replacements += 1
                replaced = True
            break
        if not replaced:
            lines.append(line)

    return "\n".join(lines) + "\n", replacements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path, help="harvested preload-summary.txt")
    parser.add_argument("report", type=Path, help="hardware-runs/vita-run-*.md report to update")
    parser.add_argument("--dry-run", action="store_true", help="print updated report instead of writing it")
    args = parser.parse_args()

    summary = load_summary(args.summary)
    updated, replacements = apply_summary(args.report.read_text(encoding="utf-8", errors="replace"), summary)

    if args.dry_run:
        print(updated, end="")
    else:
        args.report.write_text(updated, encoding="utf-8")
    print(f"updated_preload_fields={replacements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
