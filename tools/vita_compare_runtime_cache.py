#!/usr/bin/env python3
"""Compare two Vita Kart 64 runtime cache harvests.

This host-side tool is for supervised hardware iterations. It does not contact
the Vita. Point it at two harvested runtime-cache directories to see whether the
later run discovered new shaders, texture pairs, or texture misses.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path


Pair = tuple[str, str, int]
FRAME_HITCH_RE = re.compile(r"(?:^|\s)frame_ms=(?P<frame_ms>[0-9.]+)")


def load_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    result: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            result.add(line)
    return result


def load_pairs(path: Path) -> set[Pair]:
    if not path.exists():
        return set()
    result: set[Pair] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            palette_index = int(fields[2], 0) if len(fields) > 2 else 0
        except ValueError:
            palette_index = 0
        result.add((fields[0], fields[1], palette_index & 0xF))
    return result


def parse_log_line(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in shlex.split(raw, comments=False, posix=True):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        result[key] = value
    return result


def load_texture_misses(path: Path) -> set[Pair]:
    if not path.exists():
        return set()
    result: set[Pair] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = parse_log_line(raw)
        texture = fields.get("resource", "")
        palette = fields.get("palette_resource0", "") or fields.get("palette_resource1", "")
        if not texture or not palette or texture == "<raw>":
            continue
        try:
            palette_index = int(fields.get("palette", "0"), 0)
        except ValueError:
            palette_index = 0
        result.add((texture, palette, palette_index & 0xF))
    return result


def load_key_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * pct
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def bucket_counts(frame_times: list[float]) -> dict[str, int]:
    buckets = {
        "18_24_ms": 0,
        "24_33_ms": 0,
        "33_50_ms": 0,
        "50_plus_ms": 0,
    }
    for value in frame_times:
        if value >= 50.0:
            buckets["50_plus_ms"] += 1
        elif value >= 33.0:
            buckets["33_50_ms"] += 1
        elif value >= 24.0:
            buckets["24_33_ms"] += 1
        elif value >= 18.0:
            buckets["18_24_ms"] += 1
    return buckets


def load_frame_hitch_stats(path: Path) -> dict[str, float | int | bool]:
    if not path.exists():
        return {
            "present": False,
            "hitches": 0,
            "max_frame_ms": 0.0,
            "p95_frame_ms": 0.0,
            "p99_frame_ms": 0.0,
            "buckets": bucket_counts([]),
        }

    frame_times: list[float] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = FRAME_HITCH_RE.search(raw)
        if match is None:
            continue
        frame_times.append(float(match.group("frame_ms")))

    return {
        "present": True,
        "hitches": len(frame_times),
        "max_frame_ms": max(frame_times) if frame_times else 0.0,
        "p95_frame_ms": percentile(frame_times, 0.95),
        "p99_frame_ms": percentile(frame_times, 0.99),
        "buckets": bucket_counts(frame_times),
    }


def cache_snapshot(path: Path) -> dict[str, object]:
    return {
        "shaders": load_lines(path / "shader-manifest.txt"),
        "texture_pairs": load_pairs(path / "texture-pairs.manifest"),
        "texture_misses": load_texture_misses(path / "texture-misses.log"),
        "frame_hitch_stats": load_frame_hitch_stats(path / "frame-hitches.log"),
        "preload_summary": load_key_values(path / "preload-summary.txt"),
    }


def stringify_pairs(pairs: set[Pair]) -> list[str]:
    return [f"{texture} {palette} {palette_index}" for texture, palette, palette_index in sorted(pairs)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="older runtime-cache harvest directory")
    parser.add_argument("after", type=Path, help="newer runtime-cache harvest directory")
    parser.add_argument("--json-output", type=Path, help="optional JSON output path")
    parser.add_argument("--fail-on-growth", action="store_true", help="return nonzero if the newer run discovered cache entries")
    args = parser.parse_args()

    before = cache_snapshot(args.before)
    after = cache_snapshot(args.after)

    new_shaders = after["shaders"] - before["shaders"]
    new_pairs = after["texture_pairs"] - before["texture_pairs"]
    new_misses = after["texture_misses"] - before["texture_misses"]
    before_preload = before["preload_summary"]
    after_preload = after["preload_summary"]
    before_hitches = before["frame_hitch_stats"]
    after_hitches = after["frame_hitch_stats"]
    before_hitch_buckets = before_hitches.get("buckets", {})
    after_hitch_buckets = after_hitches.get("buckets", {})
    preload_changed = {
        key: {
            "before": before_preload.get(key, ""),
            "after": after_preload.get(key, ""),
        }
        for key in sorted(set(before_preload) | set(after_preload))
        if before_preload.get(key, "") != after_preload.get(key, "")
    }

    summary = {
        "before": str(args.before),
        "after": str(args.after),
        "before_counts": {
            "shaders": len(before["shaders"]),
            "texture_pairs": len(before["texture_pairs"]),
            "texture_misses": len(before["texture_misses"]),
            "frame_hitches": before_hitches.get("hitches", 0),
            "preload_summary_keys": len(before_preload),
        },
        "after_counts": {
            "shaders": len(after["shaders"]),
            "texture_pairs": len(after["texture_pairs"]),
            "texture_misses": len(after["texture_misses"]),
            "frame_hitches": after_hitches.get("hitches", 0),
            "preload_summary_keys": len(after_preload),
        },
        "growth": {
            "shaders": len(new_shaders),
            "texture_pairs": len(new_pairs),
            "texture_misses": len(new_misses),
            "preload_summary_keys": len(preload_changed),
        },
        "frame_hitch_stats": {
            "before": before_hitches,
            "after": after_hitches,
            "delta_hitches": int(after_hitches.get("hitches", 0)) - int(before_hitches.get("hitches", 0)),
            "delta_max_frame_ms": float(after_hitches.get("max_frame_ms", 0.0)) -
            float(before_hitches.get("max_frame_ms", 0.0)),
            "delta_p95_frame_ms": float(after_hitches.get("p95_frame_ms", 0.0)) -
            float(before_hitches.get("p95_frame_ms", 0.0)),
            "delta_p99_frame_ms": float(after_hitches.get("p99_frame_ms", 0.0)) -
            float(before_hitches.get("p99_frame_ms", 0.0)),
            "delta_buckets": {
                key: int(after_hitch_buckets.get(key, 0)) - int(before_hitch_buckets.get(key, 0))
                for key in sorted(set(before_hitch_buckets) | set(after_hitch_buckets))
            },
        },
        "new_shaders": sorted(new_shaders),
        "new_texture_pairs": stringify_pairs(new_pairs),
        "new_texture_misses": stringify_pairs(new_misses),
        "preload_summary_changes": preload_changed,
    }

    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)

    if args.fail_on_growth and (new_shaders or new_pairs or new_misses):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
