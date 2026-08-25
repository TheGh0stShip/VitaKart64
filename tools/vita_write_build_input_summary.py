#!/usr/bin/env python3
"""Write a concise local summary of supervised build inputs.

This is offline-only. It reads local files and environment flags, then writes a
Markdown summary for the next supervised hardware pass. It does not build,
install, launch, connect to a Vita, pull crashes, harvest caches, or validate
runtime behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


KEY_FILES = (
    "Makefile.vita",
    "mk64-vita.o2r",
    "spaghetti.o2r",
    "assets/vita/loading.png",
    "assets/vita/brand-assets.manifest.json",
    "assets/vita/shader-manifest.txt",
    "assets/vita/texture-pairs.manifest",
    "assets/vita/texture-pairs-extra.manifest",
    "livearea/icon0.png",
    "livearea/startup-vk64.png",
    "livearea/bg.png",
    "livearea/pic0.png",
    "livearea/template.xml",
    "hardware-runs/next-supervised-checklist.md",
    "hardware-runs/release-gate-digest.txt",
    "vendor/vitagl/BUILD.txt",
    "vendor/vitagl/libvitagl.a",
    "src/port/Engine.cpp",
    "libultraship/include/fast/backends/gfx_direct3d_common.h",
    "libultraship/include/fast/backends/gfx_metal.h",
    "tools/vita_after_supervised_run.sh",
    "tools/vita_apply_preload_summary_to_report.py",
    "tools/vita_apply_shader_warmup_summary_to_report.py",
    "tools/vita_collect_runtime_cache.py",
    "tools/vita_promote_runtime_cache.py",
    "tools/vita_pull_latest_crash.py",
    "tools/vita_score_hardware_run.py",
    "tools/vita_triage_supervised_run.py",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        return {"path": relative, "present": False}
    return {
        "path": relative,
        "present": True,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def count_manifest_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        count += 1 if line else 0
    return count


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def render(root: Path) -> str:
    gate_manifest = load_json(root / "docs/vita-kart-64-release-gates.json")
    brand_manifest = load_json(root / "assets/vita/brand-assets.manifest.json")
    gate_digest_path = root / "hardware-runs/release-gate-digest.txt"
    gate_digest = gate_digest_path.read_text(encoding="utf-8", errors="replace").strip() if gate_digest_path.is_file() else ""
    build_policy = gate_manifest.get("required_build_policy", {})
    runtime_gates = gate_manifest.get("required_runtime_gates", [])
    brand_assets = brand_manifest.get("assets", [])
    brand_sources = brand_manifest.get("sources", [])
    key_records = [file_record(root, relative) for relative in KEY_FILES]
    missing_key_files = [record["path"] for record in key_records if not record.get("present")]

    lines: list[str] = []
    lines.append("# Vita Kart 64 supervised build input summary")
    lines.append("")
    lines.append(f"- Created UTC: `{datetime.now(timezone.utc).isoformat()}`")
    lines.append(f"- Project root: `{root}`")
    lines.append(f"- Product: `{gate_manifest.get('product', 'Vita Kart 64')}`")
    lines.append(f"- Platform gate: `{gate_manifest.get('platform', 'PS Vita hardware')}`")
    lines.append(f"- Release gate digest: `{gate_digest}`")
    lines.append("")
    lines.append("## Environment flags")
    lines.append("")
    for name in (
        "VITAKART_SUPERVISED_HARDWARE_RUN",
        "VITAKART_REQUIRE_FULL_CI_COVERAGE",
        "VITAKART_TEXTURE_PAIR_LIMIT",
        "VITAKART_TEXTURE_MISS_LOG",
        "VITAKART_FRAME_HITCH_LOG",
        "VITAKART_FRAME_HITCH_LOG_MS",
        "VITAKART_ALLOW_DIAGNOSTIC_BUILD",
        "VITAKART_JOBS",
        "VITA_ENABLE_LTO",
        "VITA_LTO_JOBS",
    ):
        lines.append(f"- `{name}`: `{os.environ.get(name, '')}`")
    lines.append("")
    lines.append("## Release policy")
    lines.append("")
    if isinstance(build_policy, dict):
        for key in sorted(build_policy):
            lines.append(f"- `{key}`: `{build_policy[key]}`")
    lines.append("")
    lines.append("## Runtime gate count")
    lines.append("")
    gate_count = len(runtime_gates) if isinstance(runtime_gates, list) else 0
    lines.append(f"- Runtime gates: `{gate_count}`")
    if isinstance(runtime_gates, list):
        for gate in runtime_gates:
            if isinstance(gate, dict) and gate.get("id"):
                lines.append(f"- Gate `{gate.get('id')}`: evidence `{gate.get('evidence', '')}`")
    lines.append("")
    lines.append("## Manifest scale")
    lines.append("")
    lines.append(f"- Texture pairs: `{count_manifest_lines(root / 'assets/vita/texture-pairs.manifest')}`")
    lines.append(f"- Texture-pair overlay entries: `{count_manifest_lines(root / 'assets/vita/texture-pairs-extra.manifest')}`")
    lines.append(f"- Shader manifest entries: `{count_manifest_lines(root / 'assets/vita/shader-manifest.txt')}`")
    lines.append("")
    lines.append("## Brand manifest scale")
    lines.append("")
    lines.append(f"- Brand manifest schema: `{brand_manifest.get('schema', '')}`")
    lines.append(f"- Brand assets: `{len(brand_assets) if isinstance(brand_assets, list) else 0}`")
    lines.append(f"- Brand sources: `{len(brand_sources) if isinstance(brand_sources, list) else 0}`")
    lines.append("")
    lines.append("## Key file records")
    lines.append("")
    lines.append(f"- Missing key files: `{len(missing_key_files)}`")
    if missing_key_files:
        for relative in missing_key_files:
            lines.append(f"- Missing: `{relative}`")
    lines.append("")
    for record in key_records:
        relative = str(record["path"])
        if not record.get("present"):
            lines.append(f"- `{relative}`: missing")
        else:
            lines.append(f"- `{relative}`: size `{record['size']}` sha256 `{record['sha256']}`")
    lines.append("")
    lines.append("This summary is not proof of runtime behavior. It only records local build inputs before the supervised hardware pass.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "hardware-runs" / "build-input-summary.md",
        help="Output Markdown summary path.",
    )
    args = parser.parse_args()

    output = args.output
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(root), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
