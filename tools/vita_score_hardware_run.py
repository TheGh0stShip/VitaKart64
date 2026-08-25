#!/usr/bin/env python3
"""Score a filled Vita Kart 64 supervised hardware run report.

This is a host-side evidence tool. It does not build, deploy, launch, contact
the Vita, or edit the report. It turns the filled markdown checklist into a
plain next-action recommendation so hardware iterations do not depend on memory
or subjective summaries alone.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FIELD_RE = re.compile(r"^- (?P<name>[^:]+):\s*(?P<value>.*)$")


def normalize(value: str) -> str:
    return value.strip().strip("`").lower()


def load_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = FIELD_RE.match(raw.strip())
        if match is None:
            continue
        fields[normalize(match.group("name"))] = normalize(match.group("value"))
    return fields


def value_contains(fields: dict[str, str], name: str, token: str) -> bool:
    return token in fields.get(name, "")


def missing_or_unknown(fields: dict[str, str], name: str) -> bool:
    value = fields.get(name, "")
    return value == "" or "unknown" in value or "not tested" in value


def parse_int_field(fields: dict[str, str], name: str) -> int | None:
    value = fields.get(name, "")
    match = re.search(r"-?\d+", value)
    if match is None:
        return None
    try:
        return int(match.group(0), 10)
    except ValueError:
        return None


def parse_float_field(fields: dict[str, str], name: str) -> float | None:
    value = fields.get(name, "")
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def score_report(fields: dict[str, str]) -> dict[str, object]:
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    if value_contains(fields, "startup crash", "yes") or value_contains(fields, "crash occurred", "yes"):
        blockers.append("Crash occurred during supervised run.")
        next_actions.append("Pull and symbolicate the latest crash dump before performance tuning.")

    if value_contains(fields, "audio present at menu", "no") or value_contains(fields, "audio present in race", "no"):
        blockers.append("Audio is missing.")
        next_actions.append("Fix audio initialization before judging frame pacing.")

    if value_contains(fields, "right border artifact", "present") or value_contains(fields, "bottom border artifact", "present"):
        blockers.append("Viewport/framebuffer artifact is present.")
        next_actions.append("Prioritize viewport, scissor, clear, and framebuffer ownership fixes before antialiasing.")

    stutter_fields = (
        "countdown/start stutter",
        "first item/effect stutter",
        "kart-heavy scene stutter",
        "lap transition stutter",
        "first score screen stutter",
        "trophy/ceremony stutter",
    )
    severe_stutter = [name for name in stutter_fields if value_contains(fields, name, "severe")]
    minor_stutter = [name for name in stutter_fields if value_contains(fields, name, "minor")]
    if severe_stutter:
        blockers.append("Severe stutter remains: " + ", ".join(severe_stutter))
    if minor_stutter:
        warnings.append("Minor stutter remains: " + ", ".join(minor_stutter))

    if value_contains(fields, "runtime shader manifest grew", "yes") or value_contains(
        fields, "runtime texture miss log generated", "yes"
    ):
        next_actions.append("Harvest runtime cache data, preview promotion counts, promote accepted seeds, rebuild normal release, and retest.")
    elif severe_stutter or minor_stutter:
        next_actions.append("If cache harvests did not grow, investigate audio warmup, archive reads, and frame pacing.")

    if value_contains(fields, "runtime frame hitch log generated", "yes"):
        warnings.append("Frame hitch log was generated during the supervised run.")
        next_actions.append("Inspect frame-hitches.log timing around race start, item effects, and post-race transitions.")
        hitch_count = parse_int_field(fields, "frame hitch count")
        max_hitch_ms = parse_float_field(fields, "frame hitch max ms")
        p95_hitch_ms = parse_float_field(fields, "frame hitch p95 ms")
        if hitch_count is None or max_hitch_ms is None or p95_hitch_ms is None:
            warnings.append("Frame hitch log was generated but summary metrics are missing.")
            next_actions.append("Run vita_summarize_frame_hitches.py with --apply-report before scoring again.")
        else:
            warnings.append(f"Frame hitch metrics: count={hitch_count}, max_ms={max_hitch_ms:.3f}, p95_ms={p95_hitch_ms:.3f}.")
            if max_hitch_ms >= 33.0:
                blockers.append("At least one frame hitch exceeded roughly two 60 Hz frames.")
            elif hitch_count > 0:
                next_actions.append("Reduce hitch count toward zero before final release audit.")

    if value_contains(fields, "warmup benefit persisted after reopen", "no"):
        blockers.append("Warmup/cache benefit did not persist after close and reopen.")
        next_actions.append("Check packaged manifest loading and Vita-local persistent cache paths.")

    deferred_textures = parse_int_field(fields, "preload deferred textures")
    if deferred_textures is not None and deferred_textures > 0:
        warnings.append(f"Runtime preload left {deferred_textures} deferred texture entries.")
        next_actions.append("Audit deferred texture entries before assuming remaining stutter is unrelated to texture warmup.")

    audio_resources = parse_int_field(fields, "preload audio resources")
    if audio_resources == 0:
        warnings.append("Runtime preload reported zero audio resources.")
        next_actions.append("Check audio resource grouping before investigating deeper audio scheduling changes.")
    audio_warmup_banks = parse_int_field(fields, "preload audio warmup banks")
    audio_warmup_sequences = parse_int_field(fields, "preload audio warmup sequences")
    if audio_warmup_banks == 0 or audio_warmup_sequences == 0:
        warnings.append("Audio table warmup reported zero banks or sequences.")
        next_actions.append("Fix audio table warmup before treating race-start or post-race audio hitches as scheduler-only problems.")

    shader_preset_complete = fields.get("shader preset warmup complete", "")
    if shader_preset_complete in {"", "0", "false", "no"}:
        warnings.append("Shader preset warmup is missing or incomplete.")
        next_actions.append("Fix shader warmup startup coverage before chasing isolated first-use graphics hitches.")
    if value_contains(fields, "shader manifest capacity full", "1") or value_contains(
        fields, "shader manifest capacity full", "yes"
    ):
        warnings.append("Shader manifest reached capacity during warmup.")
        next_actions.append("Increase shader manifest capacity or reduce duplicate seed generation before final release.")

    if value_contains(fields, "keep full warmup", "no") or value_contains(fields, "try capped warmup next", "yes"):
        next_actions.append("Use phase planning or a texture-pair limit rather than reverting CI/TLUT preload support.")

    if value_contains(fields, "aliasing/text clarity", "needs work"):
        warnings.append("Image clarity still needs work.")
        if not blockers and not severe_stutter:
            next_actions.append("Tune filtering, viewport scaling, and optional low-cost antialiasing after stutter is solved.")

    required_fields = (
        "loading screen appears",
        "vitagl/default splash visible",
        "time to menu",
        "runtime cache ready line",
        "preload resources",
        "preload gpu textures",
        "preload ci/tlut textures",
        "preload tlut resources",
        "preload audio resources",
        "preload model resources",
        "preload other resources",
        "preload deferred textures",
        "preload resource phase ms",
        "preload ci/tlut phase ms",
        "preload audio phase ms",
        "preload total ms",
        "shader warmup summary",
        "shader manifest entries",
        "shader manifest capacity full",
        "shader preset warmup complete",
        "shader warmup compiled count",
        "preload audio warmup banks",
        "preload audio warmup sequences",
        "memory at menu",
        "audio present at menu",
        "audio present in race",
        "countdown/start stutter",
        "first score screen stutter",
        "right border artifact",
        "bottom border artifact",
        "closed and reopened",
        "warmup benefit persisted after reopen",
        "runtime frame hitch log generated",
    )
    missing = [name for name in required_fields if missing_or_unknown(fields, name)]
    if missing:
        warnings.append("Report has missing or unknown fields: " + ", ".join(missing))

    if not next_actions:
        if blockers:
            next_actions.append("Fix blockers, then rerun a supervised hardware report.")
        elif warnings:
            next_actions.append("Address warnings or run one confirmation pass before declaring release quality.")
        else:
            next_actions.append("Proceed to final release audit.")

    status = "fail" if blockers else "warn" if warnings else "pass"
    return {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "next_actions": next_actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="filled hardware-runs/vita-run-*.md report")
    parser.add_argument("--json-output", type=Path, help="optional JSON output path")
    parser.add_argument("--fail-on-not-pass", action="store_true", help="return nonzero for warn/fail")
    args = parser.parse_args()

    fields = load_fields(args.report)
    result = score_report(fields)
    result["report"] = str(args.report)

    text = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)

    if args.fail_on_not_pass and result["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
