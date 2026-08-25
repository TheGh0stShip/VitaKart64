#!/usr/bin/env python3
"""Audit CI/TLUT warmup coverage for a Vita N64 resource archive.

This is a host-side read-only tool. It does not build, deploy, contact the Vita,
or rewrite manifests. It answers a narrow question that matters for zero-stutter
hardware runs: which CI4/CI8 texture resources are not represented in the
texture-pair warmup manifests?
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

RESOURCE_PAYLOAD_OFFSET = 64
TEXTURE_RGBA16 = 2
TEXTURE_CI4 = 3
TEXTURE_CI8 = 4
CI_TYPES = {TEXTURE_CI4, TEXTURE_CI8}

Pair = tuple[str, str, int]


def texture_type(data: bytes) -> int | None:
    if len(data) < RESOURCE_PAYLOAD_OFFSET + 4:
        return None
    return int.from_bytes(data[RESOURCE_PAYLOAD_OFFSET : RESOURCE_PAYLOAD_OFFSET + 4], "little")


def load_archive_types(path: Path) -> dict[str, int | None]:
    with ZipFile(path, "r") as zf:
        return {
            name: texture_type(zf.read(name))
            for name in zf.namelist()
            if name.startswith("textures/")
        }


def load_manifest(path: Path) -> list[Pair]:
    pairs: list[Pair] = []
    if not path.exists():
        return pairs

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
        pairs.append((fields[0], fields[1], palette_index & 0xF))
    return pairs


def parent_dir(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else "."


def summarize_directories(ci_textures: set[str], paired_textures: set[str]) -> list[dict[str, int | str]]:
    by_dir: dict[str, Counter[str]] = defaultdict(Counter)
    for texture in ci_textures:
        key = parent_dir(texture)
        by_dir[key]["ci_textures"] += 1
        if texture in paired_textures:
            by_dir[key]["paired"] += 1
        else:
            by_dir[key]["unpaired"] += 1

    return [
        {
            "directory": directory,
            "ci_textures": counts["ci_textures"],
            "paired": counts["paired"],
            "unpaired": counts["unpaired"],
        }
        for directory, counts in sorted(by_dir.items(), key=lambda item: (-item[1]["unpaired"], item[0]))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=Path("mk64-vita.o2r"))
    parser.add_argument("manifest", nargs="?", type=Path, default=Path("assets/vita/texture-pairs.manifest"))
    parser.add_argument(
        "--extra-manifest",
        action="append",
        type=Path,
        default=[],
        help="additional manifest to include in the audit",
    )
    parser.add_argument(
        "--no-default-overlay",
        action="store_true",
        help="do not automatically include assets/vita/texture-pairs-extra.manifest when present",
    )
    parser.add_argument("--limit-examples", type=int, default=80, help="maximum unpaired examples to print")
    parser.add_argument("--json-output", type=Path, help="optional JSON output path")
    parser.add_argument("--fail-on-unpaired", action="store_true", help="return nonzero if any CI texture is unpaired")
    args = parser.parse_args()

    manifests = [args.manifest]
    default_overlay = Path("assets/vita/texture-pairs-extra.manifest")
    if not args.no_default_overlay and default_overlay not in manifests and default_overlay.exists():
        manifests.append(default_overlay)
    manifests.extend(args.extra_manifest)

    types = load_archive_types(args.archive)
    ci_textures = {name for name, kind in types.items() if kind in CI_TYPES}

    pairs: list[Pair] = []
    for manifest in manifests:
        pairs.extend(load_manifest(manifest))

    paired_textures = {texture for texture, _palette, _palette_index in pairs}
    unpaired = sorted(ci_textures - paired_textures)

    missing_texture_refs = sorted({texture for texture, _palette, _palette_index in pairs if texture not in types})
    missing_palette_refs = sorted({palette for _texture, palette, _palette_index in pairs if palette not in types})
    non_ci_texture_refs = sorted({texture for texture, _palette, _palette_index in pairs if types.get(texture) not in CI_TYPES})
    non_rgba16_palette_refs = sorted(
        {palette for _texture, palette, _palette_index in pairs if palette in types and types.get(palette) != TEXTURE_RGBA16}
    )

    summary = {
        "archive": str(args.archive),
        "manifests": [str(path) for path in manifests],
        "ci_textures": len(ci_textures),
        "manifest_pairs": len(pairs),
        "paired_ci_textures": len(ci_textures & paired_textures),
        "unpaired_ci_textures": len(unpaired),
        "missing_texture_refs": len(missing_texture_refs),
        "missing_palette_refs": len(missing_palette_refs),
        "non_ci_texture_refs": len(non_ci_texture_refs),
        "non_rgba16_palette_refs": len(non_rgba16_palette_refs),
        "directory_summary": summarize_directories(ci_textures, paired_textures),
        "unpaired_examples": unpaired[: max(args.limit_examples, 0)],
        "missing_texture_ref_examples": missing_texture_refs[: max(args.limit_examples, 0)],
        "missing_palette_ref_examples": missing_palette_refs[: max(args.limit_examples, 0)],
        "non_ci_texture_ref_examples": non_ci_texture_refs[: max(args.limit_examples, 0)],
        "non_rgba16_palette_ref_examples": non_rgba16_palette_refs[: max(args.limit_examples, 0)],
    }

    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)

    if args.fail_on_unpaired and unpaired:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
