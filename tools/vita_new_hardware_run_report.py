#!/usr/bin/env python3
"""Create a supervised Vita Kart 64 hardware observation report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_evidence(root: Path) -> dict[str, Any]:
    path = root / "release-evidence/latest.json"
    if not path.exists():
        return {"present": False, "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"present": False, "path": str(path), "error": str(error)}
    data["present"] = True
    data["path"] = str(path)
    return data


def artifact_lines(evidence: dict[str, Any]) -> list[str]:
    if not evidence.get("present"):
        return [f"- Release evidence: missing or unreadable at `{evidence.get('path', '')}`"]

    lines = [f"- Release evidence: `{evidence.get('path', '')}`"]
    lines.append(f"- Created UTC: `{evidence.get('created_utc', '')}`")
    clocks = evidence.get("expected_clocks_mhz", {})
    if isinstance(clocks, dict):
        lines.append(
            "- Expected clocks MHz: "
            f"ARM `{clocks.get('arm', '')}` BUS `{clocks.get('bus', '')}` "
            f"GPU `{clocks.get('gpu', '')}` XBAR `{clocks.get('gpu_xbar', '')}`"
        )
    cache_policy = evidence.get("runtime_cache_policy", {})
    if isinstance(cache_policy, dict):
        lines.append(f"- Vita texture cache max entries: `{cache_policy.get('vita_texture_cache_max_entries', '')}`")
        lines.append(
            "- Full warmup when texture pair limit is zero: "
            f"`{cache_policy.get('full_warmup_when_texture_pair_limit_zero', '')}`"
        )
    render_policy = evidence.get("render_policy", {})
    if isinstance(render_policy, dict):
        lines.append(f"- Fixed render scale: `{render_policy.get('fixed_render_scale', '')}`")
        lines.append(f"- Target FPS: `{render_policy.get('target_fps', '')}`")
        lines.append(f"- Dynamic performance profiles: `{render_policy.get('dynamic_performance_profiles', '')}`")
    generated_freshness = evidence.get("generated_metadata_freshness", {})
    if isinstance(generated_freshness, dict):
        lines.append(f"- Generated metadata current: `{generated_freshness.get('current', '')}`")
        for record in generated_freshness.get("records", []):
            if not isinstance(record, dict):
                continue
            lines.append(
                "- Generated metadata "
                f"`{record.get('label', '')}` output `{record.get('output', '')}` "
                f"present `{record.get('present', '')}` current `{record.get('current', '')}`"
            )
    release_gates = evidence.get("release_gates", {})
    if isinstance(release_gates, dict):
        manifest = release_gates.get("manifest", {})
        checklist = release_gates.get("checklist", {})
        digest_file = release_gates.get("digest_file", {})
        if isinstance(manifest, dict):
            lines.append(f"- Release gate manifest: `{manifest.get('path', '')}` present `{manifest.get('present', '')}`")
        if release_gates.get("canonical_sha256_available"):
            lines.append(f"- Release gate canonical sha256: `{release_gates.get('canonical_sha256', '')}`")
        if isinstance(digest_file, dict):
            lines.append(f"- Release gate digest file: `{digest_file.get('path', '')}` present `{digest_file.get('present', '')}`")
        if isinstance(checklist, dict):
            lines.append(f"- Supervised checklist: `{checklist.get('path', '')}` present `{checklist.get('present', '')}`")
        lines.append(f"- Release gate platform: `{release_gates.get('platform', '')}`")
        lines.append(f"- Release gate launch policy: `{release_gates.get('launch_policy', '')}`")
    brand_assets = evidence.get("brand_assets", {})
    if isinstance(brand_assets, dict):
        lines.append(f"- Brand asset manifest available: `{brand_assets.get('available', '')}`")
        lines.append(f"- Brand asset schema: `{brand_assets.get('schema', '')}`")
        lines.append(f"- Brand asset count: `{brand_assets.get('asset_count', '')}`")
        lines.append(f"- Brand source count: `{brand_assets.get('source_count', '')}`")
        for asset in brand_assets.get("assets", []):
            if not isinstance(asset, dict):
                continue
            lines.append(
                "- Brand asset "
                f"`{asset.get('path', '')}` present `{asset.get('present', '')}` "
                f"size `{asset.get('size', '')}` sha256 `{asset.get('sha256', '')}`"
            )
    for artifact in evidence.get("artifacts", []):
        if not isinstance(artifact, dict) or not artifact.get("present"):
            continue
        path = artifact.get("path", "")
        size = artifact.get("size", "")
        digest = artifact.get("sha256", "")
        lines.append(f"- `{path}` size `{size}` sha256 `{digest}`")
    stats = evidence.get("texture_manifest_stats", {})
    if isinstance(stats, dict) and stats.get("available"):
        lines.append(f"- Texture pairs: `{stats.get('pairs', '')}`")
        lines.append(f"- Texture payload estimate MiB: `{stats.get('estimated_native_rgba5551_mib', '')}`")
        lines.append(f"- Palette bounds failures: `{stats.get('palette_bounds_failures', '')}`")
    flags = evidence.get("build_flags", {})
    if isinstance(flags, dict):
        lines.append(f"- Texture miss logging: `{flags.get('VITAKART_TEXTURE_MISS_LOG', '')}`")
        lines.append(f"- Frame hitch logging: `{flags.get('VITAKART_FRAME_HITCH_LOG', '')}`")
        lines.append(f"- Frame hitch threshold ms: `{flags.get('VITAKART_FRAME_HITCH_LOG_MS', '')}`")
        lines.append(f"- Texture pair limit: `{flags.get('VITAKART_TEXTURE_PAIR_LIMIT', '')}`")
        lines.append(f"- Require full CI coverage: `{flags.get('VITAKART_REQUIRE_FULL_CI_COVERAGE', '')}`")
        lines.append(f"- LTO enabled: `{flags.get('VITA_ENABLE_LTO', '')}`")
        lines.append(f"- ccache basedir: `{flags.get('CCACHE_BASEDIR', '')}`")
        lines.append(f"- ccache nohashdir: `{flags.get('CCACHE_NOHASHDIR', '')}`")
    source_inputs = evidence.get("source_inputs", [])
    if isinstance(source_inputs, list):
        for source in source_inputs:
            if not isinstance(source, dict) or not source.get("present"):
                continue
            path = source.get("path", "")
            digest = source.get("sha256", "")
            lines.append(f"- Source input `{path}` sha256 `{digest}`")
    return lines


def write_report(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Vita Kart 64 supervised hardware run",
        "",
        f"- Report created UTC: `{now}`",
        "- Hardware: PS Vita",
        "- Title ID: `VITAKRT64`",
        "- Build type: normal / diagnostic / capped",
        "- Texture pair limit: `0` means full warmup",
        "- Release evidence should include source input hashes for cache tools, overlay manifest, build scripts, and deployment guard.",
        "- Release gate manifest/checklist/digest should be tied to this run.",
        "- Observed clocks: ARM / BUS / GPU / XBAR",
        "",
        "## Build evidence",
        "",
        *artifact_lines(evidence),
        "",
        "## Startup observations",
        "",
        "- Loading screen appears: yes / no",
        "- VitaGL/default splash visible: yes / no",
        "- Time to menu: ",
        "- Progress text advanced normally: yes / no",
        "- Runtime cache ready line: ",
        "- Preload ready marker: ",
        "- Preload skipped: ",
        "- Preload skip reason: ",
        "- Preload ready marker present before run: ",
        "- Runtime texture pair limit: ",
        "- Preload resources: ",
        "- Preload GPU textures: ",
        "- Preload CI/TLUT textures: ",
        "- Preload manifest CI/TLUT pairs attempted: ",
        "- Preload manifest CI/TLUT pairs warmed: ",
        "- Preload manifest CI/TLUT duplicate pairs: ",
        "- Preload heuristic CI/TLUT pairs attempted: ",
        "- Preload heuristic CI/TLUT pairs warmed: ",
        "- Preload heuristic CI/TLUT duplicate pairs: ",
        "- Preload audio warmup banks: ",
        "- Preload audio warmup sequences: ",
        "- Preload TLUT resources: ",
        "- Preload audio resources: ",
        "- Preload model resources: ",
        "- Preload other resources: ",
        "- Preload deferred textures: ",
        "- Reserved texture slots: ",
        "- Preload priority common/menu: ",
        "- Preload priority audio: ",
        "- Preload priority ceremony/post-race: ",
        "- Preload priority common models/other: ",
        "- Preload priority karts: ",
        "- Preload priority tracks: ",
        "- Preload priority other: ",
        "- Preload priority common/menu ms: ",
        "- Preload priority audio ms: ",
        "- Preload priority ceremony/post-race ms: ",
        "- Preload priority common models/other ms: ",
        "- Preload priority karts ms: ",
        "- Preload priority tracks ms: ",
        "- Preload priority other ms: ",
        "- Preload priority common/menu GPU ms: ",
        "- Preload priority audio GPU ms: ",
        "- Preload priority ceremony/post-race GPU ms: ",
        "- Preload priority common models/other GPU ms: ",
        "- Preload priority karts GPU ms: ",
        "- Preload priority tracks GPU ms: ",
        "- Preload priority other GPU ms: ",
        "- Preload resource phase ms: ",
        "- Preload CI/TLUT phase ms: ",
        "- Preload audio phase ms: ",
        "- Preload total ms: ",
        "- Shader warmup summary: ",
        "- Shader manifest entries: ",
        "- Shader manifest warmup index: ",
        "- Shader manifest capacity: ",
        "- Shader manifest capacity full: ",
        "- Shader preset total: ",
        "- Shader preset warmup complete: ",
        "- Shader warmup compiled count: ",
        "- Shader warmup resident count: ",
        "- Startup crash: yes / no",
        "- Memory at menu: ",
        "",
        "## Audio observations",
        "",
        "- Audio present at menu: yes / no",
        "- Audio present in race: yes / no",
        "- Dropouts or crackle: none / minor / severe",
        "",
        "## Race observations",
        "",
        "- Track/mode/character: ",
        "- Countdown/start stutter: none / minor / severe",
        "- First item/effect stutter: none / minor / severe",
        "- Kart-heavy scene stutter: none / minor / severe",
        "- Lap transition stutter: none / minor / severe",
        "- Steady race FPS: ",
        "- Worst observed FPS: ",
        "- CPU/GPU utilization notes: ",
        "",
        "## Post-race observations",
        "",
        "- First score screen stutter: none / minor / severe",
        "- Score screen smooths after time: yes / no",
        "- Trophy/ceremony stutter: none / minor / severe / not tested",
        "",
        "## Visual observations",
        "",
        "- Right border artifact: absent / present",
        "- Bottom border artifact: absent / present",
        "- Aliasing/text clarity: acceptable / needs work",
        "- Incorrect CI/TLUT colors: absent / present",
        "",
        "## Persistence observations",
        "",
        "- Closed and reopened: yes / no",
        "- Warmup benefit persisted after reopen: yes / no / not applicable",
        "- Runtime shader manifest grew: unknown / no / yes",
        "- Runtime texture miss log generated: unknown / no / yes",
        "- Runtime frame hitch log generated: unknown / no / yes",
        "- Frame hitch count: ",
        "- Frame hitch max ms: ",
        "- Frame hitch p95 ms: ",
        "- Frame hitch p99 ms: ",
        "- Frame hitch first tick ms: ",
        "- Frame hitch last tick ms: ",
        "",
        "## Crash data",
        "",
        "- Crash occurred: yes / no",
        "- Pulled dump path: ",
        "- Notes: ",
        "",
        "## Decision",
        "",
        "- Keep full warmup: yes / no",
        "- Try capped warmup next: yes / no",
        "- Need diagnostic texture-miss build: yes / no",
        "- Need crash debugging: yes / no",
        "- Primary next fix: ",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = project_root()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = args.output or root / "hardware-runs" / f"vita-run-{stamp}.md"
    write_report(output, load_evidence(root))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
