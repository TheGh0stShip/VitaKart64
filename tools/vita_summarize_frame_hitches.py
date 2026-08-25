#!/usr/bin/env python3
"""Summarize a harvested Vita Kart 64 frame-hitches.log file.

This host-side tool does not build, deploy, launch, contact the Vita, or modify
runtime data. It converts diagnostic frame-hitch logs into comparable counts and
timing metrics for supervised performance iterations.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LINE_RE = re.compile(
    r"(?:^|\s)tick_ms=(?P<tick_ms>\d+)\s+frame_ms=(?P<frame_ms>[0-9.]+)\s+ema_ms=(?P<ema_ms>[0-9.]+)\s+fps=(?P<fps>[0-9.]+)"
)
REPORT_FIELDS = {
    "Runtime frame hitch log generated": lambda result: "yes" if result["hitches"] else "no",
    "Frame hitch count": lambda result: str(result["hitches"]),
    "Frame hitch max ms": lambda result: f"{result['max_frame_ms']:.3f}",
    "Frame hitch p95 ms": lambda result: f"{result['p95_frame_ms']:.3f}",
    "Frame hitch p99 ms": lambda result: f"{result['p99_frame_ms']:.3f}",
    "Frame hitch first tick ms": lambda result: str(result["first_tick_ms"]),
    "Frame hitch last tick ms": lambda result: str(result["last_tick_ms"]),
}


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


def load_hitches(path: Path) -> list[dict[str, float]]:
    hitches: list[dict[str, float]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE_RE.search(raw)
        if match is None:
            continue
        hitches.append(
            {
                "tick_ms": float(match.group("tick_ms")),
                "frame_ms": float(match.group("frame_ms")),
                "ema_ms": float(match.group("ema_ms")),
                "fps": float(match.group("fps")),
            }
        )
    return hitches


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


def summarize(path: Path) -> dict[str, object]:
    hitches = load_hitches(path)
    frame_times = [entry["frame_ms"] for entry in hitches]
    ticks = [entry["tick_ms"] for entry in hitches]
    return {
        "path": str(path),
        "hitches": len(hitches),
        "first_tick_ms": int(min(ticks)) if ticks else 0,
        "last_tick_ms": int(max(ticks)) if ticks else 0,
        "max_frame_ms": max(frame_times) if frame_times else 0.0,
        "p50_frame_ms": percentile(frame_times, 0.50),
        "p95_frame_ms": percentile(frame_times, 0.95),
        "p99_frame_ms": percentile(frame_times, 0.99),
        "buckets": bucket_counts(frame_times),
        "first_examples": hitches[:10],
        "worst_examples": sorted(hitches, key=lambda entry: entry["frame_ms"], reverse=True)[:10],
    }


def apply_to_report(report: Path, result: dict[str, object]) -> int:
    replacements = 0
    lines: list[str] = []
    for line in report.read_text(encoding="utf-8", errors="replace").splitlines():
        replaced = False
        for label, value_func in REPORT_FIELDS.items():
            prefix = f"- {label}:"
            if line.startswith(prefix):
                lines.append(f"{prefix} {value_func(result)}")
                replacements += 1
                replaced = True
                break
        if not replaced:
            lines.append(line)

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return replacements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="harvested frame-hitches.log")
    parser.add_argument("--json-output", type=Path, help="optional JSON summary path")
    parser.add_argument("--apply-report", type=Path, help="optional hardware report to update with summary metrics")
    parser.add_argument("--fail-on-hitches", action="store_true", help="return nonzero if any hitches are present")
    args = parser.parse_args()

    result = summarize(args.log)
    if args.apply_report is not None:
        result["updated_report_fields"] = apply_to_report(args.apply_report, result)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)

    if args.fail_on_hitches and result["hitches"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
