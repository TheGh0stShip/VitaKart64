#!/usr/bin/env python3
"""Estimate Vita texture-pair warmup coverage and native texture memory."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile

PAYLOAD_OFFSET = 64
TEXTURE_CI4 = 3
TEXTURE_CI8 = 4
TYPE_NAMES = {
    1: "RGBA32",
    2: "RGBA16",
    3: "CI4",
    4: "CI8",
    5: "I4",
    6: "I8",
    7: "IA4",
    8: "IA8",
    9: "IA16",
}


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
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        pairs.append((fields[0], fields[1], int(fields[2], 0) if len(fields) > 2 else 0))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=Path("mk64-vita.o2r"))
    parser.add_argument("manifest", nargs="?", type=Path, default=Path("assets/vita/texture-pairs.manifest"))
    args = parser.parse_args()

    pairs = load_manifest(args.manifest)
    by_type: dict[int, int] = {}
    missing = 0
    palette_bounds_failures = 0
    estimated_bytes = 0

    with ZipFile(args.archive, "r") as zf:
        for texture, palette, palette_index in pairs:
            meta = texture_meta(zf, texture)
            if meta is None:
                missing += 1
                continue
            texture_type, width, height = meta
            by_type[texture_type] = by_type.get(texture_type, 0) + 1
            estimated_bytes += width * height * 2
            if texture_type in {TEXTURE_CI4, TEXTURE_CI8}:
                texture_payload_bytes = texture_payload(zf, texture)
                palette_payload_bytes = texture_payload(zf, palette)
                if texture_payload_bytes is None or palette_payload_bytes is None:
                    palette_bounds_failures += 1
                elif texture_payload_bytes:
                    max_index = max(texture_payload_bytes) if texture_type == TEXTURE_CI8 else max(
                        max(byte >> 4, byte & 0xF) for byte in texture_payload_bytes
                    )
                    palette_entries = len(palette_payload_bytes) // 2
                    if texture_type == TEXTURE_CI4 and palette_entries > 16:
                        required_entries = max_index + 1 + palette_index * 16
                    else:
                        required_entries = max_index + 1
                    if required_entries > palette_entries:
                        palette_bounds_failures += 1

    print(f"pairs: {len(pairs)}")
    print(f"missing_textures: {missing}")
    print(f"palette_bounds_failures: {palette_bounds_failures}")
    print(f"estimated_native_rgba5551_bytes: {estimated_bytes}")
    print(f"estimated_native_rgba5551_mib: {estimated_bytes / 1048576:.2f}")
    for texture_type, count in sorted(by_type.items()):
        print(f"{TYPE_NAMES.get(texture_type, str(texture_type))}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
