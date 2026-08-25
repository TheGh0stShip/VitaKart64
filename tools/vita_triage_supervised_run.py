#!/usr/bin/env python3
"""Suggest the next Vita Kart 64 fix from local supervised-run evidence.

This is intentionally offline-only. It reads files that already exist after a
supervised hardware run and prints a next-action recommendation. It does not
build, install, launch, connect to a Vita, pull logs, harvest caches, or validate
runtime behavior.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


STATUS_RE = re.compile(r"\b(PASS|FAIL|NOT TESTED)\b")
STATUS_FIELD_RE = re.compile(r"\bstatus:\s*(PASS|FAIL|NOT TESTED)\b", re.IGNORECASE)
DEFAULT_GATE_ORDER = [
    "loading_screen",
    "audio",
    "race_start_hitch",
    "race_fps",
    "post_race_scoreboard",
    "presentation_edges",
    "visual_quality",
    "warmup_persistence",
    "brand_identity",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_lines(path: Path | None) -> list[str]:
    if path is None or not path.exists() or not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def load_gate_order(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_GATE_ORDER
    if not isinstance(data, dict):
        return DEFAULT_GATE_ORDER
    gates = data.get("required_runtime_gates", [])
    if not isinstance(gates, list):
        return DEFAULT_GATE_ORDER
    gate_ids: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        gate_id = gate.get("id")
        if isinstance(gate_id, str) and gate_id:
            gate_ids.append(gate_id)
    return gate_ids or DEFAULT_GATE_ORDER


def parse_status(line: str) -> str | None:
    status_field = STATUS_FIELD_RE.search(line)
    if status_field:
        return status_field.group(1).upper()
    matches = STATUS_RE.findall(line)
    if not matches:
        return None
    unique = set(matches)
    if {"PASS", "FAIL", "NOT TESTED"}.issubset(unique):
        return None
    if "FAIL" in unique:
        return "FAIL"
    if "NOT TESTED" in unique:
        return "NOT TESTED"
    if "PASS" in unique:
        return "PASS"
    return None


def gate_status(lines: list[str], gate_id: str) -> str:
    needle = f"`{gate_id}`"
    for line in lines:
        if needle in line:
            status = parse_status(line)
            if status:
                return status
    return "NOT TESTED"


def count_data_lines(lines: list[str]) -> int:
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def count_hitches(lines: list[str]) -> int:
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "frame_ms" in stripped and "tick_ms" in stripped:
            continue
        if re.search(r"\d", stripped):
            count += 1
    return count


def normalized_manifest_lines(lines: list[str]) -> set[str]:
    values: set[str] = set()
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if line:
            values.add(line)
    return values


def count_promotable_lines(runtime_path: Path | None, packaged_path: Path | None) -> int:
    runtime_lines = normalized_manifest_lines(read_lines(runtime_path))
    packaged_lines = normalized_manifest_lines(read_lines(packaged_path))
    return len(runtime_lines - packaged_lines)


def read_preload_summary(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def print_evidence_summary(args: argparse.Namespace) -> tuple[int, int, int, int, dict[str, str]]:
    texture_miss_lines = read_lines(args.texture_misses)
    frame_hitch_lines = read_lines(args.frame_hitches)
    preload_summary = read_preload_summary(read_lines(args.preload_summary))
    preload_ready = read_preload_summary(read_lines(args.preload_ready))
    preload_reentry = read_preload_summary(read_lines(args.preload_reentry))
    shader_warmup = read_preload_summary(read_lines(args.shader_warmup_summary))

    texture_misses = count_data_lines(texture_miss_lines)
    frame_hitches = count_hitches(frame_hitch_lines)
    promotable_shader_seeds = count_promotable_lines(args.runtime_shader_manifest, args.packaged_shader_manifest)
    promotable_texture_pairs = count_promotable_lines(args.runtime_texture_pairs, args.packaged_texture_pairs)

    print("Evidence summary:")
    print(f"- checklist: {args.checklist if args.checklist and args.checklist.exists() else 'missing'}")
    print(f"- preload summary: {args.preload_summary if args.preload_summary and args.preload_summary.exists() else 'missing'}")
    print(f"- preload ready marker: {args.preload_ready if args.preload_ready and args.preload_ready.exists() else 'missing'}")
    print(f"- preload reentry: {args.preload_reentry if args.preload_reentry and args.preload_reentry.exists() else 'missing'}")
    print(f"- shader warmup summary: {args.shader_warmup_summary if args.shader_warmup_summary and args.shader_warmup_summary.exists() else 'missing'}")
    print(f"- texture misses: {texture_misses}")
    print(f"- frame hitches: {frame_hitches}")
    print(f"- promotable shader seeds: {promotable_shader_seeds}")
    print(f"- promotable texture pairs: {promotable_texture_pairs}")
    if preload_summary:
        for key in [
            "resident_resources",
            "preload_skipped",
            "preload_skip_reason",
            "preload_ready_marker",
            "preload_ready_marker_present_before_run",
            "texture_pair_limit",
            "texture_resources",
            "model_resources",
            "audio_resources",
            "other_resources",
            "gpu_textures",
            "paletted_gpu_textures",
            "paletted_manifest_pairs_attempted",
            "paletted_manifest_pairs_warmed",
            "paletted_manifest_pairs_duplicate",
            "paletted_heuristic_pairs_attempted",
            "paletted_heuristic_pairs_warmed",
            "paletted_heuristic_pairs_duplicate",
            "audio_warmup_banks",
            "audio_warmup_sequences",
            "deferred_textures",
            "reserved_texture_slots",
            "preload_priority_common_menu",
            "preload_priority_audio",
            "preload_priority_ceremony",
            "preload_priority_common_models",
            "preload_priority_karts",
            "preload_priority_tracks",
            "preload_priority_other",
            "preload_priority_common_menu_ms",
            "preload_priority_audio_ms",
            "preload_priority_ceremony_ms",
            "preload_priority_common_models_ms",
            "preload_priority_karts_ms",
            "preload_priority_tracks_ms",
            "preload_priority_other_ms",
            "preload_priority_common_menu_gpu_ms",
            "preload_priority_audio_gpu_ms",
            "preload_priority_ceremony_gpu_ms",
            "preload_priority_common_models_gpu_ms",
            "preload_priority_karts_gpu_ms",
            "preload_priority_tracks_gpu_ms",
            "preload_priority_other_gpu_ms",
            "audio_phase_ms",
            "total_ms",
        ]:
            if key in preload_summary:
                print(f"- {key}: {preload_summary[key]}")
    if preload_ready:
        print(f"- preload_ready_schema: {preload_ready.get('schema', '')}")
        print(f"- preload_ready_total_ms: {preload_ready.get('total_ms', '')}")
        print(f"- preload_ready_paletted_manifest_pairs_warmed: {preload_ready.get('paletted_manifest_pairs_warmed', '')}")
        print(f"- preload_ready_paletted_heuristic_pairs_warmed: {preload_ready.get('paletted_heuristic_pairs_warmed', '')}")
        print(f"- preload_ready_audio_warmup_banks: {preload_ready.get('audio_warmup_banks', '')}")
        print(f"- preload_ready_audio_warmup_sequences: {preload_ready.get('audio_warmup_sequences', '')}")
    if preload_reentry:
        print(f"- preload_reentry_skipped: {preload_reentry.get('preload_reentry_skipped', '')}")
        print(f"- preload_reentry_reason: {preload_reentry.get('preload_reentry_reason', '')}")
    if shader_warmup:
        for key in [
            "schema",
            "shader_manifest_entries",
            "shader_manifest_warmup_index",
            "shader_manifest_capacity",
            "shader_manifest_capacity_full",
            "shader_preset_total",
            "shader_preset_warmup_complete",
            "shader_warmup_compiled_any",
            "shader_warmup_compiled_count",
            "shader_warmup_resident_count",
        ]:
            if key in shader_warmup:
                print(f"- shader_warmup_{key}: {shader_warmup[key]}")
    print("")
    return texture_misses, frame_hitches, promotable_shader_seeds, promotable_texture_pairs, preload_summary


def recommend_from_gates(
    statuses: dict[str, str],
    texture_misses: int,
    frame_hitches: int,
    promotable_shader_seeds: int,
    promotable_texture_pairs: int,
    gate_order: list[str],
) -> list[str]:
    recommendations: list[str] = []

    if statuses.get("loading_screen") == "FAIL":
        recommendations.append("Fix loading UX/vendor splash policy before performance work.")
    if statuses.get("presentation_edges") == "FAIL":
        recommendations.append("Freeze performance changes and fix viewport/scissor/framebuffer presentation policy first.")
    if statuses.get("audio") == "FAIL":
        recommendations.append("Fix audio output/resource setup before chasing frame pacing.")
    if statuses.get("race_fps") == "FAIL":
        recommendations.append("Treat this as a baseline performance regression; avoid image-quality upgrades until 60 fps is restored.")

    race_hitch_failed = statuses.get("race_start_hitch") == "FAIL"
    post_race_failed = statuses.get("post_race_scoreboard") == "FAIL"
    if race_hitch_failed or post_race_failed:
        if promotable_shader_seeds > 0 or promotable_texture_pairs > 0:
            recommendations.append("Promote supervised runtime cache discoveries into packaged warmup manifests, rebuild supervised, then retest.")
        elif texture_misses > 0:
            recommendations.append("Merge only supervised hardware-discovered texture/TLUT misses into the persistent overlay, rebuild supervised, then retest.")
        elif frame_hitches > 0:
            recommendations.append("Use the frame-hitch timestamps to map spikes to race-start, item, multi-kart, or post-race phases; add targeted resource/shader/audio prewarm for that phase.")
        else:
            recommendations.append("Run one supervised frame-hitch diagnostic build with texture-miss logging off; current evidence says hitches exist but does not locate them.")

    if statuses.get("visual_quality") == "FAIL" and not any(
        statuses.get(gate) == "FAIL"
        for gate in ["race_start_hitch", "race_fps", "post_race_scoreboard", "presentation_edges"]
    ):
        recommendations.append("Explore selective UI/text filtering or presentation sampling; do not enable heavier antialiasing unless the supervised frame-time floor remains stable.")
    if statuses.get("brand_identity") == "FAIL":
        recommendations.append("Fix packaged Vita Kart 64 icon/startup/loading identity assets before calling the artifact polished.")
    if statuses.get("warmup_persistence") == "FAIL":
        recommendations.append("Compare first-launch and close/reopen preload-ready marker evidence; if hitches return, prioritize persistent shader/resource seed packaging before new renderer changes.")

    if not recommendations:
        if all(statuses.get(gate) == "PASS" for gate in gate_order):
            recommendations.append("All runtime gates are marked PASS. Score the filled checklist and bundle evidence for the candidate artifact.")
        else:
            recommendations.append("Complete the missing checklist gates on PS Vita hardware before choosing the next fix.")

    return recommendations


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checklist",
        type=Path,
        default=root / "hardware-runs" / "next-supervised-checklist.md",
        help="Filled supervised-run checklist.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "docs" / "vita-kart-64-release-gates.json",
        help="Release gate JSON manifest.",
    )
    parser.add_argument(
        "--preload-summary",
        type=Path,
        default=root / "runtime-cache" / "latest" / "preload-summary.txt",
        help="Pulled preload summary, if present.",
    )
    parser.add_argument(
        "--preload-ready",
        type=Path,
        default=root / "runtime-cache" / "latest" / "preload-ready.marker",
        help="Pulled preload-ready marker, if present.",
    )
    parser.add_argument(
        "--preload-reentry",
        type=Path,
        default=root / "runtime-cache" / "latest" / "preload-reentry.txt",
        help="Pulled preload re-entry sidecar, if present.",
    )
    parser.add_argument(
        "--texture-misses",
        type=Path,
        default=root / "runtime-cache" / "latest" / "texture-misses.log",
        help="Pulled texture misses, if present.",
    )
    parser.add_argument(
        "--frame-hitches",
        type=Path,
        default=root / "runtime-cache" / "latest" / "frame-hitches.log",
        help="Pulled frame hitch log, if present.",
    )
    parser.add_argument(
        "--shader-warmup-summary",
        type=Path,
        default=root / "runtime-cache" / "latest" / "shader-warmup-summary.txt",
        help="Pulled shader warmup summary, if present.",
    )
    parser.add_argument(
        "--runtime-shader-manifest",
        type=Path,
        default=root / "runtime-cache" / "latest" / "shader-manifest.txt",
        help="Pulled runtime shader manifest, if present.",
    )
    parser.add_argument(
        "--runtime-texture-pairs",
        type=Path,
        default=root / "runtime-cache" / "latest" / "texture-pairs.manifest",
        help="Pulled runtime texture-pairs manifest, if present.",
    )
    parser.add_argument(
        "--packaged-shader-manifest",
        type=Path,
        default=root / "assets" / "vita" / "shader-manifest.txt",
        help="Packaged shader manifest.",
    )
    parser.add_argument(
        "--packaged-texture-pairs",
        type=Path,
        default=root / "assets" / "vita" / "texture-pairs.manifest",
        help="Packaged texture-pairs manifest.",
    )
    args = parser.parse_args()

    checklist_lines = read_lines(args.checklist)
    gate_order = load_gate_order(args.manifest)
    statuses = {gate: gate_status(checklist_lines, gate) for gate in gate_order}

    print("Vita Kart 64 supervised-run triage")
    print("")
    print("Checklist gates:")
    for gate in gate_order:
        print(f"- {gate}: {statuses[gate]}")
    print("")

    texture_misses, frame_hitches, promotable_shader_seeds, promotable_texture_pairs, _preload = print_evidence_summary(args)
    recommendations = recommend_from_gates(
        statuses,
        texture_misses,
        frame_hitches,
        promotable_shader_seeds,
        promotable_texture_pairs,
        gate_order,
    )

    print("Recommended next action:")
    for item in recommendations:
        print(f"- {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
