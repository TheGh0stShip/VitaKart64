#!/usr/bin/env python3
"""Host-only preflight for a supervised Vita Kart 64 build.

This script intentionally does not compile, contact the Vita, install, or launch.
It checks local prerequisites and summarizes warmup-manifest scale before a supervised hardware iteration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

PAYLOAD_OFFSET = 64
TEXTURE_CI4 = 3
TEXTURE_CI8 = 4
DEFAULT_VDB_ROOT = Path(os.environ.get("VDB_ROOT", str(Path.home() / "projects" / "VitaDevBridge")))
DEFAULT_VDB_CONFIG = Path(os.environ["VDB_CONFIG"]) if os.environ.get("VDB_CONFIG") else DEFAULT_VDB_ROOT / ".vitadevbridge" / "your-paired-vita.toml"
DEFAULT_VITASDK = Path("/usr/local/vitasdk")
DEFAULT_MAKE_PYTHON = Path(".venv/bin/python")
REQUIRED_PROJECT_FILES = (
    "Makefile.vita",
    "mk64-vita.o2r",
    "spaghetti.o2r",
    "assets/vita/shader-manifest.txt",
    "assets/vita/texture-pairs-extra.manifest",
    "livearea/bg.png",
    "livearea/pic0.png",
    "livearea/template.xml",
    "vendor/vitagl/BUILD.txt",
    "vendor/vitagl/libvitagl.a",
    "tools/vita_build_vitagl_vendor.sh",
    "tools/vita_build_install_frame_hitch_stopped.sh",
    "tools/vita_build_install_diagnostic_stopped.sh",
    "tools/vita_build_install_stopped.sh",
    "tools/vita_prepare_supervised_release.sh",
    "tools/vita_promote_runtime_cache.py",
    "tools/vita_deploy_release.sh",
    "tools/vita_after_supervised_run.sh",
    "tools/vita_apply_preload_summary_to_report.py",
    "tools/vita_apply_shader_warmup_summary_to_report.py",
    "tools/vita_audit_archive_layout.py",
    "tools/vita_audit_texture_pair_coverage.py",
    "tools/vita_collect_runtime_cache.py",
    "tools/vita_compare_runtime_cache.py",
    "tools/vita_generate_brand_assets.sh",
    "tools/vita_generate_icon_art.py",
    "tools/vita_generate_livearea_art.py",
    "tools/vita_generate_loading_art.py",
    "tools/vita_generate_release_gate_checklist.py",
    "tools/vita_generate_texture_pairs.py",
    "tools/vita_hash_release_gates.py",
    "tools/vita_index_png.py",
    "tools/vita_merge_shader_manifest.py",
    "tools/vita_merge_texture_misses.py",
    "tools/vita_new_hardware_run_report.py",
    "tools/vita_plan_cache_phases.py",
    "tools/vita_plan_resource_warmup.py",
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
GENERATED_PROJECT_FILES = (
    "assets/vita/loading.png",
    "assets/vita/brand-assets.manifest.json",
    "assets/vita/texture-pairs.manifest",
    "hardware-runs/next-supervised-checklist.md",
    "hardware-runs/release-gate-digest.txt",
    "livearea/icon0.png",
    "livearea/startup-vk64.png",
)
REQUIRED_VITA_TOOLS = (
    "arm-vita-eabi-gcc",
    "arm-vita-eabi-g++",
    "vita-make-fself",
    "vita-mksfoex",
    "vita-pack-vpk",
)
CRITICAL_TEXTURE_PREFIXES = (
    "textures/common_data/",
    "textures/ceremony_data/",
    "textures/player_selection/",
    "textures/startup_logo/",
)
REQUIRED_VITAGL_FLAGS = (
    "HAVE_SHADER_CACHE=1",
    "NO_DEBUG=1",
    "USE_SCRATCH_MEMORY=1",
    "SAMPLERS_SPEEDHACK=1",
    "NO_SPLASHSCREEN=1",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def status_line(ok: bool, label: str, detail: str = "") -> None:
    prefix = "OK" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"{prefix}: {label}{suffix}")


def parse_bool_flag(name: str, value: str) -> tuple[int, bool]:
    if value in {"0", "1"}:
        status_line(True, name, value)
        return int(value), True
    status_line(False, name, f"expected 0 or 1, got {value!r}")
    return 0, False


def parse_nonnegative_int_flag(name: str, value: str) -> tuple[int, bool]:
    try:
        parsed = int(value, 0)
    except ValueError:
        status_line(False, name, f"expected nonnegative integer, got {value!r}")
        return 0, False
    if parsed < 0:
        status_line(False, name, f"expected nonnegative integer, got {parsed}")
        return 0, False
    status_line(True, name, str(parsed))
    return parsed, True


def parse_positive_int_flag(name: str, value: str) -> tuple[int, bool]:
    try:
        parsed = int(value, 0)
    except ValueError:
        status_line(False, name, f"expected positive integer, got {value!r}")
        return 0, False
    if parsed <= 0:
        status_line(False, name, f"expected positive integer, got {parsed}")
        return 0, False
    status_line(True, name, str(parsed))
    return parsed, True


def parse_optional_bool_flag(name: str, value: str) -> tuple[bool, bool]:
    if value == "1":
        status_line(True, name, "1")
        return True, True
    if value == "0":
        status_line(True, name, "0")
        return False, True
    status_line(False, name, f"expected 0 or 1, got {value!r}")
    return False, False


def texture_meta(zf: ZipFile, path: str) -> tuple[int, int, int] | None:
    try:
        data = zf.read(path)
    except KeyError:
        return None
    if len(data) < PAYLOAD_OFFSET + 12:
        return None
    texture_type = int.from_bytes(data[PAYLOAD_OFFSET : PAYLOAD_OFFSET + 4], "little")
    width = int.from_bytes(data[PAYLOAD_OFFSET + 4 : PAYLOAD_OFFSET + 8], "little")
    height = int.from_bytes(data[PAYLOAD_OFFSET + 8 : PAYLOAD_OFFSET + 12], "little")
    return texture_type, width, height


def texture_payload(zf: ZipFile, path: str) -> bytes | None:
    try:
        data = zf.read(path)
    except KeyError:
        return None
    if len(data) < PAYLOAD_OFFSET + 28:
        return None
    image_size = int.from_bytes(data[PAYLOAD_OFFSET + 24 : PAYLOAD_OFFSET + 28], "little")
    start = PAYLOAD_OFFSET + 28
    end = start + image_size
    if end > len(data):
        return None
    return data[start:end]


def load_manifest(path: Path) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        palette_index = int(fields[2], 0) if len(fields) > 2 else 0
        pairs.append((fields[0], fields[1], palette_index & 0xF))
    return pairs


def is_critical_texture(path: str) -> bool:
    return path.startswith(CRITICAL_TEXTURE_PREFIXES)


def check_manifest_order(pairs: list[tuple[str, str, int]]) -> int:
    first_bulk_index = None
    for index, pair in enumerate(pairs):
        if not is_critical_texture(pair[0]):
            first_bulk_index = index
            break

    if first_bulk_index is None:
        status_line(True, "manifest priority order", "critical-only")
        return 0

    for texture, _palette, _palette_index in pairs[first_bulk_index:]:
        if is_critical_texture(texture):
            status_line(False, "manifest priority order", f"late critical texture={texture}")
            return 1

    status_line(True, "manifest priority order", f"first_bulk_index={first_bulk_index}")
    return 0


def check_project_files(root: Path, include_generated: bool) -> int:
    failures = 0
    required = REQUIRED_PROJECT_FILES + (GENERATED_PROJECT_FILES if include_generated else ())
    for relative in required:
        path = root / relative
        ok = path.is_file()
        status_line(ok, relative)
        failures += 0 if ok else 1
    return failures


def check_make_python(root: Path) -> int:
    configured = os.environ.get("PYTHON")
    if configured and "/" not in configured:
        resolved = shutil.which(configured)
        ok = resolved is not None
        status_line(ok, "Makefile PYTHON", configured if resolved is None else resolved)
        return 0 if ok else 1

    path = Path(configured) if configured else DEFAULT_MAKE_PYTHON
    if not path.is_absolute():
        path = root / path
    ok = path.is_file() and os.access(path, os.X_OK)
    status_line(ok, "Makefile PYTHON", str(path))
    return 0 if ok else 1


def check_makefile_release_policy(root: Path) -> int:
    path = root / "Makefile.vita"
    if not path.is_file():
        status_line(False, "Makefile release policy", str(path))
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    required_fragments = (
        "TARGET := Vita Kart 64",
        "TITLE := VITAKRT64",
        'SPAGHETTI_VERSION="\\"VK64 1.0.0\\""',
        "VITAKART_BUILD_CONFIG := build/vita_build_config.h",
        "-include $(VITAKART_BUILD_CONFIG)",
        "VITAKART_TEXTURE_PAIR_LIMIT ?= 0",
        "assets/vita/loading.png",
        "assets/vita/brand-assets.manifest.json",
        "assets/vita/shader-manifest.txt",
        "assets/vita/texture-pairs.manifest",
        "livearea/icon0.png",
        "livearea/startup-vk64.png",
        "livearea-indexed/icon0.png=sce_sys/icon0.png",
        "livearea-indexed/startup.png=sce_sys/livearea/contents/startup.png",
        "assets/vita/loading.png=loading.png",
        "assets/vita/brand-assets.manifest.json=brand-assets.manifest.json",
        "assets/vita/shader-manifest.txt=shader-manifest.txt",
        "assets/vita/texture-pairs.manifest=texture-pairs.manifest",
        "spaghetti.o2r=spaghetti.o2r",
    )
    missing = [fragment for fragment in required_fragments if fragment not in text]
    status_line(not missing, "Makefile release policy", "missing=" + ",".join(missing) if missing else "required fragments present")
    return 1 if missing else 0


def check_vitasdk(vitasdk: Path) -> int:
    failures = 0
    bin_dir = vitasdk / "bin"
    status_line(bin_dir.is_dir(), "VITASDK bin", str(bin_dir))
    failures += 0 if bin_dir.is_dir() else 1
    for tool in REQUIRED_VITA_TOOLS:
        path = bin_dir / tool
        ok = path.is_file() and os.access(path, os.X_OK)
        status_line(ok, tool, str(path))
        failures += 0 if ok else 1
    return failures


def check_vdb(vdb_root: Path, vdb_config: Path) -> int:
    failures = 0
    status_line(vdb_root.is_dir(), "VitaDevBridge root", str(vdb_root))
    failures += 0 if vdb_root.is_dir() else 1
    status_line((vdb_root / "src/vitadevbridge").is_dir(), "VitaDevBridge Python package")
    failures += 0 if (vdb_root / "src/vitadevbridge").is_dir() else 1
    status_line(vdb_config.is_file(), "VitaDevBridge config", str(vdb_config))
    failures += 0 if vdb_config.is_file() else 1
    return failures


def check_vitagl_policy(root: Path) -> int:
    build_txt = root / "vendor/vitagl/BUILD.txt"
    if not build_txt.is_file():
        status_line(False, "vitaGL build policy", str(build_txt))
        return 1
    text = build_txt.read_text(encoding="utf-8", errors="replace")
    missing = [flag for flag in REQUIRED_VITAGL_FLAGS if flag not in text]
    status_line(not missing, "vitaGL build policy", "missing=" + ",".join(missing) if missing else "required flags present")
    return 1 if missing else 0


def check_release_build_policy(
    root: Path,
    texture_miss_log: int,
    frame_hitch_log: int,
    texture_pair_limit: int,
    require_full_ci_coverage: bool,
    include_generated: bool,
    allow_diagnostic_build: bool,
) -> int:
    path = root / "docs/vita-kart-64-release-gates.json"
    if not path.is_file():
        status_line(False, "release build policy manifest", str(path))
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        status_line(False, "release build policy manifest", str(error))
        return 1
    if not isinstance(data, dict):
        status_line(False, "release build policy manifest", "expected JSON object")
        return 1
    policy = data.get("required_build_policy", {})
    if not isinstance(policy, dict):
        status_line(False, "release build policy", "required_build_policy must be an object")
        return 1

    failures = 0

    expected_full_ci = bool(policy.get("full_ci_tlut_coverage", False))
    ok = (not expected_full_ci) or require_full_ci_coverage
    status_line(ok, "release policy full CI/TLUT coverage", f"expected={expected_full_ci} actual={require_full_ci_coverage}")
    failures += 0 if ok else 1

    expected_pair_limit = policy.get("texture_pair_limit")
    if expected_pair_limit is not None:
        ok = texture_pair_limit == int(expected_pair_limit)
        status_line(ok, "release policy texture pair limit", f"expected={expected_pair_limit} actual={texture_pair_limit}")
        failures += 0 if ok else 1

    expected_texture_miss_log = bool(policy.get("texture_miss_log_release", False))
    ok = bool(texture_miss_log) == expected_texture_miss_log or allow_diagnostic_build
    status_line(
        ok,
        "release policy texture miss log",
        f"expected={expected_texture_miss_log} actual={bool(texture_miss_log)} allow_diagnostic={allow_diagnostic_build}",
    )
    failures += 0 if ok else 1

    expected_frame_hitch_log = bool(policy.get("frame_hitch_log_release", False))
    ok = bool(frame_hitch_log) == expected_frame_hitch_log or allow_diagnostic_build
    status_line(
        ok,
        "release policy frame hitch log",
        f"expected={expected_frame_hitch_log} actual={bool(frame_hitch_log)} allow_diagnostic={allow_diagnostic_build}",
    )
    failures += 0 if ok else 1

    expected_splash = policy.get("middleware_splash")
    ok = expected_splash in (None, "disabled")
    status_line(ok, "release policy middleware splash", f"expected={expected_splash} actual=checked-by-vitaGL-policy")
    failures += 0 if ok else 1

    expected_brand_assets = bool(policy.get("brand_assets_generated", False))
    if include_generated:
        ok = (not expected_brand_assets) or all(
            (root / relative).is_file()
            for relative in ("assets/vita/loading.png", "livearea/icon0.png", "livearea/startup-vk64.png")
        )
        status_line(ok, "release policy brand assets generated", f"expected={expected_brand_assets}")
        failures += 0 if ok else 1
    else:
        status_line(True, "release policy brand assets generated", "deferred-to-full-preflight")

    expected_brand_manifest = bool(policy.get("brand_asset_manifest", False))
    if include_generated:
        ok = (not expected_brand_manifest) or (root / "assets/vita/brand-assets.manifest.json").is_file()
        status_line(ok, "release policy brand asset manifest", f"expected={expected_brand_manifest}")
        failures += 0 if ok else 1
    else:
        status_line(True, "release policy brand asset manifest", "deferred-to-full-preflight")

    return failures


def check_manifest_freshness(root: Path) -> int:
    manifest = root / "assets/vita/texture-pairs.manifest"
    inputs = (
        root / "mk64-vita.o2r",
        root / "tools/vita_generate_texture_pairs.py",
        root / "assets/vita/texture-pairs-extra.manifest",
    )
    if not manifest.is_file():
        status_line(False, "texture-pairs.manifest freshness", "manifest missing")
        return 1

    manifest_mtime = manifest.stat().st_mtime
    stale_inputs = [str(path.relative_to(root)) for path in inputs if path.is_file() and path.stat().st_mtime > manifest_mtime]
    status_line(
        not stale_inputs,
        "texture-pairs.manifest freshness",
        "stale_after=" + ",".join(stale_inputs) if stale_inputs else "current",
    )
    return 1 if stale_inputs else 0


def check_generated_freshness(root: Path, label: str, output_relative: str, input_relatives: tuple[str, ...]) -> int:
    output = root / output_relative
    inputs = tuple(root / relative for relative in input_relatives)
    if not output.is_file():
        status_line(False, label, "missing=" + output_relative)
        return 1

    output_mtime = output.stat().st_mtime
    stale_inputs = [str(path.relative_to(root)) for path in inputs if path.is_file() and path.stat().st_mtime > output_mtime]
    status_line(not stale_inputs, label, "stale_after=" + ",".join(stale_inputs) if stale_inputs else "current")
    return 1 if stale_inputs else 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_brand_asset_manifest_contents(root: Path) -> int:
    path = root / "assets/vita/brand-assets.manifest.json"
    if not path.is_file():
        status_line(False, "brand-assets.manifest contents", "manifest missing")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        status_line(False, "brand-assets.manifest contents", str(error))
        return 1

    failures = 0
    if not isinstance(data, dict):
        status_line(False, "brand-assets.manifest contents", "expected JSON object")
        return 1
    status_line(
        data.get("schema") == "vitakart64.brand-assets.v1",
        "brand-assets.manifest schema",
        str(data.get("schema", "")),
    )
    failures += 0 if data.get("schema") == "vitakart64.brand-assets.v1" else 1

    for group in ("assets", "sources"):
        records = data.get(group, [])
        if not isinstance(records, list):
            status_line(False, f"brand-assets.manifest {group}", "expected list")
            failures += 1
            continue
        for record in records:
            if not isinstance(record, dict):
                status_line(False, f"brand-assets.manifest {group}", "expected object record")
                failures += 1
                continue
            relative = str(record.get("path", ""))
            item = root / relative
            present = item.is_file()
            expected_present = bool(record.get("present"))
            ok = present and expected_present
            detail = relative if ok else f"{relative} present={present} manifest_present={expected_present}"
            status_line(ok, f"brand-assets.manifest {group} presence", detail)
            failures += 0 if ok else 1
            if not ok:
                continue

            size = item.stat().st_size
            expected_size = record.get("size")
            size_ok = size == expected_size
            status_line(size_ok, f"brand-assets.manifest {group} size", f"{relative} size={size} manifest={expected_size}")
            failures += 0 if size_ok else 1

            digest = sha256_file(item)
            expected_digest = record.get("sha256")
            digest_ok = digest == expected_digest
            status_line(digest_ok, f"brand-assets.manifest {group} sha256", relative)
            failures += 0 if digest_ok else 1
    return failures


def check_brand_asset_freshness(root: Path) -> int:
    failures = 0
    failures += check_generated_freshness(
        root,
        "loading brand asset freshness",
        "assets/vita/loading.png",
        ("tools/vita_generate_loading_art.py",),
    )
    failures += check_generated_freshness(
        root,
        "icon brand asset freshness",
        "livearea/icon0.png",
        ("tools/vita_generate_icon_art.py", "tools/vita_generate_loading_art.py"),
    )
    failures += check_generated_freshness(
        root,
        "startup brand asset freshness",
        "livearea/startup-vk64.png",
        ("tools/vita_generate_livearea_art.py", "tools/vita_generate_loading_art.py"),
    )
    failures += check_generated_freshness(
        root,
        "brand-assets.manifest freshness",
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
    )
    failures += check_brand_asset_manifest_contents(root)
    return failures


def check_release_gate_metadata_freshness(root: Path) -> int:
    failures = 0
    failures += check_generated_freshness(
        root,
        "release checklist freshness",
        "hardware-runs/next-supervised-checklist.md",
        (
            "docs/vita-kart-64-release-gates.json",
            "tools/vita_generate_release_gate_checklist.py",
        ),
    )
    failures += check_generated_freshness(
        root,
        "release gate digest freshness",
        "hardware-runs/release-gate-digest.txt",
        (
            "docs/vita-kart-64-release-gates.json",
            "tools/vita_hash_release_gates.py",
        ),
    )
    return failures


def summarize_manifest(root: Path, pair_limit: int, require_full_ci_coverage: bool) -> int:
    archive = root / "mk64-vita.o2r"
    manifest = root / "assets/vita/texture-pairs.manifest"
    failures = 0
    try:
        pairs = load_manifest(manifest)
    except Exception as error:
        status_line(False, "texture-pairs.manifest parse", str(error))
        return 1

    failures += check_manifest_freshness(root)
    failures += check_manifest_order(pairs)

    limit = pair_limit if pair_limit > 0 else len(pairs)
    selected = pairs[:limit]
    missing = 0
    palette_bounds_failures = 0
    estimated_bytes = 0
    ci4 = 0
    ci8 = 0
    try:
        with ZipFile(archive, "r") as zf:
            ci_textures = set()
            for name in zf.namelist():
                if not name.startswith("textures/"):
                    continue
                meta = texture_meta(zf, name)
                if meta is not None and meta[0] in {TEXTURE_CI4, TEXTURE_CI8}:
                    ci_textures.add(name)

            for texture, _palette, _palette_index in selected:
                meta = texture_meta(zf, texture)
                if meta is None:
                    missing += 1
                    continue
                texture_type, width, height = meta
                ci4 += 1 if texture_type == TEXTURE_CI4 else 0
                ci8 += 1 if texture_type == TEXTURE_CI8 else 0
                if texture_type in {TEXTURE_CI4, TEXTURE_CI8}:
                    texture_payload_bytes = texture_payload(zf, texture)
                    palette_payload_bytes = texture_payload(zf, _palette)
                    if texture_payload_bytes is None or palette_payload_bytes is None:
                        palette_bounds_failures += 1
                    elif texture_payload_bytes:
                        max_index = max(texture_payload_bytes) if texture_type == TEXTURE_CI8 else max(
                            max(byte >> 4, byte & 0xF) for byte in texture_payload_bytes
                        )
                        palette_entries = len(palette_payload_bytes) // 2
                        if texture_type == TEXTURE_CI4 and palette_entries > 16:
                            required_entries = max_index + 1 + _palette_index * 16
                        else:
                            required_entries = max_index + 1
                        if required_entries > palette_entries:
                            palette_bounds_failures += 1
                estimated_bytes += width * height * 2

            paired_ci_textures = ci_textures & {texture for texture, _palette, _palette_index in pairs}
            unpaired_ci_textures = ci_textures - paired_ci_textures
    except Exception as error:
        status_line(False, "manifest archive scan", str(error))
        return 1

    status_line(
        not require_full_ci_coverage or len(unpaired_ci_textures) == 0,
        "CI/TLUT coverage",
        f"ci={len(ci_textures)} paired={len(paired_ci_textures)} unpaired={len(unpaired_ci_textures)}",
    )
    failures += 1 if require_full_ci_coverage and unpaired_ci_textures else 0
    status_line(missing == 0, "manifest paths", f"missing={missing}")
    failures += 0 if missing == 0 else 1
    status_line(palette_bounds_failures == 0, "manifest palette bounds", f"failures={palette_bounds_failures}")
    failures += 0 if palette_bounds_failures == 0 else 1
    print(f"INFO: ci_textures={len(ci_textures)}")
    print(f"INFO: paired_ci_textures={len(paired_ci_textures)}")
    print(f"INFO: unpaired_ci_textures={len(unpaired_ci_textures)}")
    print(f"INFO: manifest_pairs={len(pairs)}")
    print(f"INFO: effective_pair_limit={pair_limit}")
    print(f"INFO: selected_pairs={len(selected)}")
    print(f"INFO: selected_ci4={ci4}")
    print(f"INFO: selected_ci8={ci8}")
    print(f"INFO: estimated_native_rgba5551_mib={estimated_bytes / 1048576:.2f}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vitasdk", type=Path, default=Path(os.environ.get("VITASDK", DEFAULT_VITASDK)))
    parser.add_argument("--vdb-root", type=Path, default=Path(os.environ.get("VDB_ROOT", DEFAULT_VDB_ROOT)))
    parser.add_argument("--vdb-config", type=Path, default=Path(os.environ.get("VDB_CONFIG", DEFAULT_VDB_CONFIG)))
    parser.add_argument("--texture-pair-limit", default=os.environ.get("VITAKART_TEXTURE_PAIR_LIMIT", "0"))
    parser.add_argument("--setup-only", action="store_true", help="check source/tool setup before generated manifests exist")
    args = parser.parse_args()

    root = project_root()
    failures = 0
    print(f"INFO: project_root={root}")
    print(f"INFO: python={sys.executable}")
    print(f"INFO: ccache={shutil.which('ccache') or ''}")
    texture_miss_log, ok = parse_bool_flag("VITAKART_TEXTURE_MISS_LOG", os.environ.get("VITAKART_TEXTURE_MISS_LOG", "0"))
    failures += 0 if ok else 1
    frame_hitch_log, ok = parse_bool_flag("VITAKART_FRAME_HITCH_LOG", os.environ.get("VITAKART_FRAME_HITCH_LOG", "0"))
    failures += 0 if ok else 1
    _frame_hitch_threshold, ok = parse_positive_int_flag(
        "VITAKART_FRAME_HITCH_LOG_MS", os.environ.get("VITAKART_FRAME_HITCH_LOG_MS", "18")
    )
    failures += 0 if ok else 1
    texture_pair_limit, ok = parse_nonnegative_int_flag("VITAKART_TEXTURE_PAIR_LIMIT", str(args.texture_pair_limit))
    failures += 0 if ok else 1
    require_full_ci_coverage, ok = parse_optional_bool_flag(
        "VITAKART_REQUIRE_FULL_CI_COVERAGE", os.environ.get("VITAKART_REQUIRE_FULL_CI_COVERAGE", "0")
    )
    failures += 0 if ok else 1
    allow_diagnostic_build, ok = parse_optional_bool_flag(
        "VITAKART_ALLOW_DIAGNOSTIC_BUILD", os.environ.get("VITAKART_ALLOW_DIAGNOSTIC_BUILD", "0")
    )
    failures += 0 if ok else 1
    failures += check_release_build_policy(
        root,
        texture_miss_log,
        frame_hitch_log,
        texture_pair_limit,
        require_full_ci_coverage,
        not args.setup_only,
        allow_diagnostic_build,
    )
    failures += check_project_files(root, include_generated=not args.setup_only)
    failures += check_make_python(root)
    failures += check_makefile_release_policy(root)
    failures += check_vitasdk(args.vitasdk)
    failures += check_vdb(args.vdb_root, args.vdb_config)
    failures += check_vitagl_policy(root)
    if not args.setup_only:
        failures += check_brand_asset_freshness(root)
        failures += check_release_gate_metadata_freshness(root)
        failures += summarize_manifest(root, texture_pair_limit, require_full_ci_coverage)

    if failures:
        print(f"FAIL: preflight failures={failures}", file=sys.stderr)
        return 1
    print("OK: host-only supervised build preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
