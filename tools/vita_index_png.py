#!/usr/bin/env python3
"""Convert Vita LiveArea PNGs to indexed/palette PNGs for VitaShell installs."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def convert_png(source: Path, destination: Path) -> None:
    image = Image.open(source)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, (0, 0, 0, 0))
        background.alpha_composite(image)
        image = background.convert("RGB")

    indexed = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    indexed.save(destination, "PNG", optimize=True)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: vita_index_png.py SOURCE DESTINATION", file=sys.stderr)
        return 2
    convert_png(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
