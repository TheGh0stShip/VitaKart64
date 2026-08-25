#!/usr/bin/env python3
"""Promote supervised runtime cache discoveries into durable warmup seeds.

This is a host-side file merge helper. It does not build, install, launch,
connect to a Vita, pull logs, or validate behavior. Run it only after a
supervised hardware cache harvest has populated runtime-cache/latest/.

Shader IDs are merged into assets/vita/shader-manifest.txt. Hardware-discovered
CI/TLUT texture pairs are merged into assets/vita/texture-pairs-extra.manifest
so generated texture-pairs.manifest refreshes do not erase supervised findings.
"""

from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalized_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.add(line)
    return lines


@dataclass(frozen=True, order=True)
class TexturePair:
    texture: str
    palette: str
    palette_index: int = 0

    @classmethod
    def parse(cls, raw: str) -> "TexturePair | None":
        line = raw.split("#", 1)[0].strip()
        if not line:
            return None
        parts = line.split()
        if len(parts) < 2:
            return None
        palette_index = 0
        if len(parts) >= 3:
            try:
                palette_index = int(parts[2], 0) & 0xF
            except ValueError:
                return None
        return cls(parts[0], parts[1], palette_index)

    def serialize(self) -> str:
        return f"{self.texture} {self.palette} {self.palette_index}"


def load_texture_pairs(path: Path) -> set[TexturePair]:
    if not path.exists():
        return set()
    pairs: set[TexturePair] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        pair = TexturePair.parse(raw)
        if pair is not None:
            pairs.add(pair)
    return pairs


def pairs_from_texture_misses(path: Path) -> set[TexturePair]:
    if not path.exists():
        return set()
    pairs: set[TexturePair] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields: dict[str, str] = {}
        for token in shlex.split(raw, comments=False, posix=True):
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            fields[key] = value
        texture = fields.get("resource", "")
        palette = fields.get("palette_resource0", "") or fields.get("palette_resource1", "")
        if not texture or not palette or texture == "<raw>":
            continue
        try:
            palette_index = int(fields.get("palette", "0"), 0) & 0xF
        except ValueError:
            palette_index = 0
        pairs.add(TexturePair(texture, palette, palette_index))
    return pairs


def write_manifest(path: Path, header: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines)
    path.write_text(f"{header.rstrip()}\n{body}\n", encoding="utf-8")


def promote_shader_manifest(cache_dir: Path, target: Path, dry_run: bool) -> tuple[int, int, int]:
    existing = normalized_lines(target)
    discovered = normalized_lines(cache_dir / "shader-manifest.txt")
    merged = sorted(existing | discovered)
    added = len(set(merged) - existing)
    if not dry_run and to_overlay:
        write_manifest(
            target,
            "# Vita Kart 64 packaged shader warmup manifest\n# Promoted from supervised PS Vita runtime cache.",
            merged,
        )
    return len(existing), len(discovered), added


def promote_texture_pairs(cache_dir: Path, generated: Path, overlay: Path, dry_run: bool) -> tuple[int, int, int]:
    generated_pairs = load_texture_pairs(generated)
    overlay_pairs = load_texture_pairs(overlay)
    existing = generated_pairs | overlay_pairs
    discovered = load_texture_pairs(cache_dir / "texture-pairs.manifest")
    discovered |= pairs_from_texture_misses(cache_dir / "texture-misses.log")
    to_overlay = sorted(overlay_pairs | (discovered - existing))
    added = len((discovered - existing) - overlay_pairs)
    if not dry_run and merged:
        write_manifest(
            overlay,
            "# Vita Kart 64 packaged CI/TLUT warmup pairs\n# Promoted from generated manifests and supervised PS Vita runtime cache.",
            [pair.serialize() for pair in to_overlay],
        )
    return len(existing), len(discovered), added


def main() -> int:
    root = project_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=root / "runtime-cache" / "latest")
    parser.add_argument("--shader-target", type=Path, default=root / "assets" / "vita" / "shader-manifest.txt")
    parser.add_argument(
        "--texture-generated",
        type=Path,
        default=root / "assets" / "vita" / "texture-pairs.manifest",
        help="Generated full texture-pair manifest used for existing coverage checks.",
    )
    parser.add_argument(
        "--texture-overlay",
        type=Path,
        default=root / "assets" / "vita" / "texture-pairs-extra.manifest",
        help="Durable hardware-discovered texture-pair overlay to update.",
    )
    parser.add_argument("--dry-run", action="store_true", help="report merge counts without writing files")
    args = parser.parse_args()

    shader_existing, shader_discovered, shader_added = promote_shader_manifest(
        args.cache_dir, args.shader_target, args.dry_run
    )
    texture_existing, texture_discovered, texture_added = promote_texture_pairs(
        args.cache_dir, args.texture_generated, args.texture_overlay, args.dry_run
    )

    print(f"shader_existing={shader_existing}")
    print(f"shader_discovered={shader_discovered}")
    print(f"shader_added={shader_added}")
    print(f"texture_pairs_existing={texture_existing}")
    print(f"texture_pairs_discovered={texture_discovered}")
    print(f"texture_pairs_added={texture_added}")
    print(f"dry_run={1 if args.dry_run else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
