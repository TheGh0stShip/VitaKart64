#!/usr/bin/env python3
"""Bundle local supervised-run evidence into one zip file.

This is intentionally offline-only. It packages files that already exist in the
working tree after a supervised hardware run. It does not build, install, launch,
connect to a Vita, pull logs, harvest caches, or validate runtime behavior.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import zipfile
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_output(root: Path) -> Path:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    return root / "release-evidence" / "bundles" / f"vita-kart-64-evidence-{stamp}.zip"


def add_if_exists(paths: list[Path], root: Path, relative: str) -> None:
    path = root / relative
    if path.exists() and path.is_file():
        paths.append(path)


def add_glob(paths: list[Path], root: Path, pattern: str) -> None:
    for path in root.glob(pattern):
        if path.exists() and path.is_file():
            paths.append(path)


def collect_paths(root: Path) -> list[Path]:
    paths: list[Path] = []

    fixed_files = [
        "docs/vita-kart-64-release-gates.json",
        "docs/vita-release-gate-schema.md",
        "docs/next-supervised-vita-run.md",
        "docs/next-supervised-build-change-log.md",
        "docs/unattended-work-handoff.md",
        "docs/vita-kart-64-final-polish-strategy.md",
        "docs/vita-n64-porting-research.md",
        "docs/vita-n64-porting-playbook.md",
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
        "release-evidence/latest.json",
        "hardware-runs/release-gate-digest.txt",
        "hardware-runs/build-input-summary.md",
        "tools/vita_prepare_supervised_release.sh",
        "tools/vita_build_install_stopped.sh",
        "tools/vita_after_supervised_run.sh",
        "tools/vita_deploy_release.sh",
        "tools/vita_apply_preload_summary_to_report.py",
        "tools/vita_apply_shader_warmup_summary_to_report.py",
        "tools/vita_collect_runtime_cache.py",
        "tools/vita_promote_runtime_cache.py",
        "tools/vita_pull_latest_crash.py",
        "tools/vita_score_hardware_run.py",
        "tools/vita_triage_supervised_run.py",
        "tools/vita_preflight_supervised_build.py",
        "tools/vita_write_release_evidence.py",
        "tools/vita_new_hardware_run_report.py",
        "tools/vita_require_supervised_hardware_run.sh",
        "assets/vita/loading.png",
        "assets/vita/brand-assets.manifest.json",
        "tools/vita_generate_brand_assets.sh",
        "livearea/bg.png",
        "livearea/icon0.png",
        "livearea/pic0.png",
        "livearea/startup-vk64.png",
        "livearea/template.xml",
        "livearea-indexed/icon0.png",
        "livearea-indexed/pic0.png",
        "livearea-indexed/bg.png",
        "tools/vita_generate_icon_art.py",
        "tools/vita_generate_loading_art.py",
        "livearea-indexed/startup.png",
        "tools/vita_generate_livearea_art.py",
        "tools/vita_write_brand_asset_manifest.py",
        "tools/vita_write_build_input_summary.py",
        "tools/vita_index_png.py",
        "tools/vita_print_release_readiness_index.sh",
        "assets/vita/texture-pairs.manifest",
        "assets/vita/texture-pairs-extra.manifest",
        "assets/vita/shader-manifest.txt",
        "build/vita_build_config.h",
        "vendor/vitagl/BUILD.txt",
    ]
    for relative in fixed_files:
        add_if_exists(paths, root, relative)

    glob_patterns = [
        "hardware-runs/*.md",
        "hardware-runs/*.json",
        "hardware-runs/*.txt",
        "runtime-cache/**/*.txt",
        "runtime-cache/**/*.log",
        "runtime-cache/**/*.manifest",
        "runtime-cache/**/*.marker",
        "runtime-cache/**/*.json",
        "crashes/*.psp2dmp",
        "crashes/*.txt",
        "*.vpk",
        "*.sha256",
    ]
    for pattern in glob_patterns:
        add_glob(paths, root, pattern)

    unique: dict[str, Path] = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if relative.startswith("release-evidence/bundles/"):
            continue
        unique[relative] = path
    return [unique[key] for key in sorted(unique)]


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output(root),
        help="Output zip path.",
    )
    args = parser.parse_args()

    output = args.output
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    paths = collect_paths(root)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(root).as_posix())

    print(f"Wrote {output}")
    print(f"Included {len(paths)} files")
    if not paths:
        print("Warning: no evidence files were found")
    return 0


if __name__ == "__main__":
    os.chdir(repo_root())
    raise SystemExit(main())
