#!/usr/bin/env python3
"""Write local release evidence for a Vita Kart 64 build.

This script is intended to run after a future supervised build and before/after
install. It records artifact hashes and cache-manifest scale so hardware
observations can be tied to exact build inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ARTIFACTS = (
    "eboot.bin",
    "vita-kart-64.vpk",
    "assets/vita/loading.png",
    "assets/vita/brand-assets.manifest.json",
    "assets/vita/shader-manifest.txt",
    "assets/vita/texture-pairs.manifest",
    "livearea/bg.png",
    "livearea/icon0.png",
    "livearea/pic0.png",
    "livearea/startup-vk64.png",
    "livearea/template.xml",
    "livearea-indexed/icon0.png",
    "livearea-indexed/pic0.png",
    "livearea-indexed/bg.png",
    "livearea-indexed/startup.png",
)
OPTIONAL_ARTIFACTS = (
    "mk64-vita.o2r",
    "spaghetti.o2r",
    "hardware-runs/build-input-summary.md",
)
RELEASE_GATE_MANIFEST = "docs/vita-kart-64-release-gates.json"
RELEASE_GATE_CHECKLIST = "hardware-runs/next-supervised-checklist.md"
RELEASE_GATE_DIGEST = "hardware-runs/release-gate-digest.txt"
BRAND_ASSET_MANIFEST = "assets/vita/brand-assets.manifest.json"
SOURCE_INPUTS = (
    "Makefile.vita",
    "docs/vita-kart-64-release-gates.json",
    "docs/vita-release-gate-schema.md",
    "docs/vita-n64-support-package-architecture.md",
    "docs/vita-n64-support-extraction-map.md",
    "docs/vita-kart-64-polish-backlog.md",
    "docs/vita-kart-64-release-readiness-index.md",
    "docs/vita-n64-final-polish-optimization-catalog.md",
    "src/port/Engine.cpp",
    "src/port/VitaPlatform.cpp",
    "src/port/VitaPreload.cpp",
    "src/port/VitaLoadingScreen.cpp",
    "libultraship/include/fast/interpreter.h",
    "libultraship/src/fast/interpreter.cpp",
    "libultraship/include/fast/backends/gfx_rendering_api.h",
    "libultraship/include/fast/backends/gfx_opengl.h",
    "libultraship/include/fast/backends/gfx_direct3d_common.h",
    "libultraship/include/fast/backends/gfx_metal.h",
    "libultraship/src/fast/backends/gfx_opengl.cpp",
    "assets/vita/texture-pairs-extra.manifest",
    "vendor/vitagl/BUILD.txt",
    "vendor/vitagl/libvitagl.a",
    "tools/vita_after_supervised_run.sh",
    "tools/vita_apply_preload_summary_to_report.py",
    "tools/vita_apply_shader_warmup_summary_to_report.py",
    "tools/vita_build_vitagl_vendor.sh",
    "tools/vita_audit_archive_layout.py",
    "tools/vita_audit_texture_pair_coverage.py",
    "tools/vita_build_install_frame_hitch_stopped.sh",
    "tools/vita_build_install_diagnostic_stopped.sh",
    "tools/vita_build_install_stopped.sh",
    "tools/vita_bundle_supervised_evidence.py",
    "tools/vita_collect_runtime_cache.py",
    "tools/vita_compare_runtime_cache.py",
    "tools/vita_deploy_release.sh",
    "tools/vita_generate_release_gate_checklist.py",
    "tools/vita_generate_icon_art.py",
    "tools/vita_generate_brand_assets.sh",
    "tools/vita_generate_loading_art.py",
    "tools/vita_generate_livearea_art.py",
    "tools/vita_generate_texture_pairs.py",
    "tools/vita_hash_release_gates.py",
    "tools/vita_index_png.py",
    "tools/vita_merge_shader_manifest.py",
    "tools/vita_merge_texture_misses.py",
    "tools/vita_new_hardware_run_report.py",
    "tools/vita_plan_cache_phases.py",
    "tools/vita_plan_resource_warmup.py",
    "tools/vita_prepare_supervised_release.sh",
    "tools/vita_promote_runtime_cache.py",
    "tools/vita_preflight_supervised_build.py",
    "tools/vita_print_morning_run_plan.sh",
    "tools/vita_print_release_readiness_index.sh",
    "tools/vita_print_unattended_hold_status.sh",
    "tools/vita_pull_latest_crash.py",
    "tools/vita_require_supervised_hardware_run.sh",
    "tools/vita_score_release_gate_checklist.py",
    "tools/vita_score_hardware_run.py",
    "tools/vita_summarize_frame_hitches.py",
    "tools/vita_triage_supervised_run.py",
    "tools/vita_texture_manifest_stats.py",
    "tools/vita_write_brand_asset_manifest.py",
    "tools/vita_write_build_input_summary.py",
    "tools/vita_write_release_evidence.py",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_record(root: Path, relative: str, required: bool) -> dict[str, object]:
    path = root / relative
    if not path.exists():
        return {"path": relative, "present": False, "required": required}
    return {
        "path": relative,
        "present": True,
        "required": required,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def manifest_stats(root: Path) -> dict[str, object]:
    script = root / "tools/vita_texture_manifest_stats.py"
    archive = root / "mk64-vita.o2r"
    manifest = root / "assets/vita/texture-pairs.manifest"
    if not script.exists() or not archive.exists() or not manifest.exists():
        return {"available": False}

    proc = subprocess.run(
        [sys.executable, str(script), str(archive), str(manifest)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return {"available": False, "error": proc.stderr.strip() or proc.stdout.strip()}

    parsed: dict[str, object] = {"available": True}
    for line in proc.stdout.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if value.replace(".", "", 1).isdigit():
            parsed[key] = float(value) if "." in value else int(value)
        else:
            parsed[key] = value
    return parsed


def generated_freshness_record(root: Path, label: str, output_relative: str, input_relatives: tuple[str, ...]) -> dict[str, object]:
    output = root / output_relative
    record: dict[str, object] = {
        "label": label,
        "output": output_relative,
        "present": output.is_file(),
        "current": False,
        "stale_after": [],
    }
    if not output.is_file():
        return record

    output_mtime = output.stat().st_mtime
    stale_inputs = [relative for relative in input_relatives if (root / relative).is_file() and (root / relative).stat().st_mtime > output_mtime]
    record["current"] = not stale_inputs
    record["stale_after"] = stale_inputs
    return record


def generated_metadata_freshness(root: Path) -> dict[str, object]:
    records = [
        generated_freshness_record(
            root,
            "loading brand asset",
            "assets/vita/loading.png",
            ("tools/vita_generate_loading_art.py",),
        ),
        generated_freshness_record(
            root,
            "icon brand asset",
            "livearea/icon0.png",
            ("tools/vita_generate_icon_art.py", "tools/vita_generate_loading_art.py"),
        ),
        generated_freshness_record(
            root,
            "startup brand asset",
            "livearea/startup-vk64.png",
            ("tools/vita_generate_livearea_art.py", "tools/vita_generate_loading_art.py"),
        ),
        generated_freshness_record(
            root,
            "indexed LiveArea icon",
            "livearea-indexed/icon0.png",
            ("livearea/icon0.png", "tools/vita_index_png.py"),
        ),
        generated_freshness_record(
            root,
            "indexed LiveArea pic0",
            "livearea-indexed/pic0.png",
            ("livearea/pic0.png", "tools/vita_index_png.py"),
        ),
        generated_freshness_record(
            root,
            "indexed LiveArea background",
            "livearea-indexed/bg.png",
            ("livearea/bg.png", "tools/vita_index_png.py"),
        ),
        generated_freshness_record(
            root,
            "indexed LiveArea startup",
            "livearea-indexed/startup.png",
            ("livearea/startup-vk64.png", "tools/vita_index_png.py"),
        ),
        generated_freshness_record(
            root,
            "brand asset manifest",
            "assets/vita/brand-assets.manifest.json",
            (
                "assets/vita/loading.png",
                "livearea/icon0.png",
                "livearea/startup-vk64.png",
                "tools/vita_generate_brand_assets.sh",
                "tools/vita_generate_loading_art.py",
                "tools/vita_generate_livearea_art.py",
                "tools/vita_generate_icon_art.py",
                "tools/vita_write_brand_asset_manifest.py",
            ),
        ),
        generated_freshness_record(
            root,
            "release gate checklist",
            "hardware-runs/next-supervised-checklist.md",
            ("docs/vita-kart-64-release-gates.json", "tools/vita_generate_release_gate_checklist.py"),
        ),
        generated_freshness_record(
            root,
            "release gate digest",
            "hardware-runs/release-gate-digest.txt",
            ("docs/vita-kart-64-release-gates.json", "tools/vita_hash_release_gates.py"),
        ),
        generated_freshness_record(
            root,
            "texture pair manifest",
            "assets/vita/texture-pairs.manifest",
            (
                "mk64-vita.o2r",
                "tools/vita_generate_texture_pairs.py",
                "assets/vita/texture-pairs-extra.manifest",
            ),
        ),
    ]
    stale = [record for record in records if not record.get("present") or not record.get("current")]
    return {
        "available": True,
        "current": len(stale) == 0,
        "records": records,
        "stale_or_missing": stale,
    }


def release_gate_metadata(root: Path) -> dict[str, object]:
    manifest = root / RELEASE_GATE_MANIFEST
    metadata: dict[str, object] = {
        "manifest": artifact_record(root, RELEASE_GATE_MANIFEST, True),
        "checklist": artifact_record(root, RELEASE_GATE_CHECKLIST, False),
        "digest_file": artifact_record(root, RELEASE_GATE_DIGEST, False),
    }
    if not manifest.exists():
        metadata["canonical_sha256_available"] = False
        return metadata
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    except Exception as error:
        metadata["canonical_sha256_available"] = False
        metadata["error"] = str(error)
        return metadata
    metadata["canonical_sha256_available"] = True
    metadata["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
    if isinstance(data, dict):
        metadata["product"] = data.get("product", "")
        metadata["platform"] = data.get("platform", "")
        metadata["supervised_only"] = data.get("supervised_only", "")
        metadata["launch_policy"] = data.get("launch_policy", "")
    return metadata


def brand_asset_metadata(root: Path) -> dict[str, object]:
    path = root / BRAND_ASSET_MANIFEST
    metadata: dict[str, object] = {
        "manifest": artifact_record(root, BRAND_ASSET_MANIFEST, True),
        "available": False,
    }
    if not path.exists():
        return metadata
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        metadata["error"] = str(error)
        return metadata
    if not isinstance(data, dict):
        metadata["error"] = "expected JSON object"
        return metadata
    assets = data.get("assets", [])
    sources = data.get("sources", [])
    metadata["available"] = True
    metadata["schema"] = data.get("schema", "")
    metadata["created_utc"] = data.get("created_utc", "")
    metadata["asset_count"] = len(assets) if isinstance(assets, list) else 0
    metadata["source_count"] = len(sources) if isinstance(sources, list) else 0
    metadata["assets"] = assets if isinstance(assets, list) else []
    metadata["sources"] = sources if isinstance(sources, list) else []
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = project_root()
    output = args.output or root / "release-evidence/latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    freshness = generated_metadata_freshness(root)
    if not freshness.get("current"):
        for record in freshness.get("stale_or_missing", []):
            if not isinstance(record, dict):
                continue
            print(
                "FAIL: generated metadata not current: "
                f"{record.get('label', '')} output={record.get('output', '')} "
                f"present={record.get('present', '')} stale_after={record.get('stale_after', [])}",
                file=sys.stderr,
            )
        return 1

    evidence = {
        "schema": "vitakart64.release-evidence.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "title_id": "VITAKRT64",
        "expected_clocks_mhz": {
            "arm": 500,
            "bus": 222,
            "gpu": 222,
            "gpu_xbar": 166,
        },
        "runtime_cache_policy": {
            "vita_texture_cache_max_entries": 24576,
            "default_texture_pair_limit": os.environ.get("VITAKART_TEXTURE_PAIR_LIMIT", "0"),
            "full_warmup_when_texture_pair_limit_zero": True,
            "texture_miss_logging_release_default": "0",
        },
        "render_policy": {
            "fixed_render_scale": "1/2",
            "dynamic_performance_profiles": False,
            "target_fps": 60,
        },
        "build_flags": {
            "VITAKART_TEXTURE_MISS_LOG": os.environ.get("VITAKART_TEXTURE_MISS_LOG", "0"),
            "VITAKART_FRAME_HITCH_LOG": os.environ.get("VITAKART_FRAME_HITCH_LOG", "0"),
            "VITAKART_FRAME_HITCH_LOG_MS": os.environ.get("VITAKART_FRAME_HITCH_LOG_MS", "18"),
            "VITAKART_TEXTURE_PAIR_LIMIT": os.environ.get("VITAKART_TEXTURE_PAIR_LIMIT", "0"),
            "VITAKART_ALLOW_DIAGNOSTIC_BUILD": os.environ.get("VITAKART_ALLOW_DIAGNOSTIC_BUILD", "0"),
            "VITA_ENABLE_LTO": os.environ.get("VITA_ENABLE_LTO", "1"),
            "VITA_LTO_JOBS": os.environ.get("VITA_LTO_JOBS", "8"),
            "CCACHE_BASEDIR": os.environ.get("CCACHE_BASEDIR", ""),
            "CCACHE_NOHASHDIR": os.environ.get("CCACHE_NOHASHDIR", ""),
            "VITAKART_SUPERVISED_HARDWARE_RUN": os.environ.get("VITAKART_SUPERVISED_HARDWARE_RUN", "0"),
            "VITAKART_REQUIRE_FULL_CI_COVERAGE": os.environ.get("VITAKART_REQUIRE_FULL_CI_COVERAGE", "0"),
        },
        "generated_metadata_freshness": freshness,
        "artifacts": [artifact_record(root, rel, True) for rel in ARTIFACTS]
        + [artifact_record(root, rel, False) for rel in OPTIONAL_ARTIFACTS],
        "brand_assets": brand_asset_metadata(root),
        "release_gates": release_gate_metadata(root),
        "source_inputs": [artifact_record(root, rel, True) for rel in SOURCE_INPUTS],
        "texture_manifest_stats": manifest_stats(root),
    }

    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
