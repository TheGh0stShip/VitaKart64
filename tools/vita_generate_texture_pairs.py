#!/usr/bin/env python3
"""Generate Vita CI/TLUT warmup pair hints from an O2R/OTR zip archive.

The output is intentionally simple and game-portable:

    <texture_path> <palette_path> <palette_index>

Runtime code validates resource types before uploading, so this tool can be
conservative and path-based. It is meant to seed startup warmup; supervised
runtime miss logs can later be merged through an overlay manifest.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from zipfile import ZipFile

RESOURCE_PAYLOAD_OFFSET = 64
TEXTURE_RGBA16 = 2
TEXTURE_CI4 = 3
TEXTURE_CI8 = 4
KART_FRAME_RE = re.compile(r"^(?P<kart>.+)_frame(?P<frame>\d{3})_wheel(?P<wheel>\d+)$")


def texture_type(data: bytes) -> int | None:
    if len(data) < RESOURCE_PAYLOAD_OFFSET + 4:
        return None
    return int.from_bytes(data[RESOURCE_PAYLOAD_OFFSET : RESOURCE_PAYLOAD_OFFSET + 4], "little")


def starts(value: str, prefix: str) -> bool:
    return value.startswith(prefix)


def trim_variant_suffix(suffix: str) -> str:
    if "_" not in suffix:
        return suffix
    head, tail = suffix.rsplit("_", 1)
    if tail.isdigit():
        return head
    if len(tail) == 2 and tail[0] in "1234" and tail[1] == "p":
        return head
    return suffix


def matching_palette(path: str, names: set[str]) -> str | None:
    directory, base = path.rsplit("/", 1)
    directory += "/"

    kart_frame = KART_FRAME_RE.match(base)
    if kart_frame is not None:
        candidate = (
            directory
            + kart_frame.group("kart")
            + "_"
            + kart_frame.group("frame")
            + "_tlut_wheel_"
            + kart_frame.group("wheel")
        )
        if candidate in names:
            return candidate

    if starts(base, "common_texture_"):
        tlut_prefix = "common_tlut_"
        suffix = base[len("common_texture_") :]
    elif starts(base, "texture_"):
        tlut_prefix = "tlut_"
        suffix = base[len("texture_") :]
    else:
        return None

    while suffix:
        candidate = directory + tlut_prefix + suffix
        if candidate in names:
            return candidate
        trimmed = trim_variant_suffix(suffix)
        if trimmed == suffix:
            break
        suffix = trimmed

    if base == "common_texture_portrait_question_mark":
        candidate = directory + "common_tlut_portrait_bomb_kart_and_question_mark"
        if candidate in names:
            return candidate

    return None


def pair_sort_key(pair: tuple[str, str, int]) -> tuple[int, int, str, int, str]:
    texture, _palette, _palette_index = pair
    directory, base = texture.rsplit("/", 1)

    if directory == "textures/common_data":
        return (0, 0, base, 0, texture)
    if directory == "textures/ceremony_data":
        return (1, 0, base, 0, texture)
    if directory == "textures/player_selection":
        return (2, 0, base, 0, texture)
    if directory == "textures/startup_logo":
        return (3, 0, base, 0, texture)

    kart_frame = KART_FRAME_RE.match(base)
    if kart_frame is not None:
        return (
            4,
            int(kart_frame.group("frame")),
            kart_frame.group("kart"),
            int(kart_frame.group("wheel")),
            texture,
        )

    if directory == "textures/boo_frames":
        return (5, 0, base, 0, texture)
    return (9, 0, base, 0, texture)


def generate_pairs(archive: Path) -> list[tuple[str, str, int]]:
    with ZipFile(archive, "r") as zf:
        names = {name for name in zf.namelist() if name.startswith("textures/")}
        types = {name: texture_type(zf.read(name)) for name in names}

    pairs: list[tuple[str, str, int]] = []
    for name in sorted(names):
        if types.get(name) not in {TEXTURE_CI4, TEXTURE_CI8}:
            continue
        palette = matching_palette(name, names)
        if palette is not None and types.get(palette) == TEXTURE_RGBA16:
            pairs.append((name, palette, 0))

    return sorted(pairs, key=pair_sort_key)


def load_manifest(path: Path) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    if not path.exists():
        return pairs

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


def unique_preserving_order(pairs: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    result: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        result.append(pair)
    return result


def write_manifest(pairs: list[tuple[str, str, int]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Vita Kart 64 CI/TLUT texture warmup manifest\n")
        fh.write("# format: <texture_path> <palette_path> <palette_index>\n")
        fh.write("# generated from archive paths plus persistent overlay manifests\n")
        for texture, palette, palette_index in pairs:
            fh.write(f"{texture} {palette} {palette_index}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=Path("mk64-vita.o2r"))
    parser.add_argument("output", nargs="?", type=Path, default=Path("assets/vita/texture-pairs.manifest"))
    parser.add_argument(
        "--extra",
        action="append",
        type=Path,
        default=[],
        help="additional manifest overlay to append after generated pairs",
    )
    args = parser.parse_args()

    pairs = generate_pairs(args.archive)
    for extra in args.extra:
        pairs.extend(load_manifest(extra))
    pairs = unique_preserving_order(pairs)
    write_manifest(pairs, args.output)
    print(f"wrote {len(pairs)} texture/TLUT pairs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
