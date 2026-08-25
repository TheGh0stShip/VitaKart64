#!/usr/bin/env python3
"""Generate deterministic Vita Kart 64 icon art.

This is local asset generation only. It does not build, install, launch,
connect to a Vita, harvest caches, pull crashes, or validate runtime behavior.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vita_generate_loading_art import Canvas  # noqa: E402


SIZE = 128


def draw_icon_badge(canvas: Canvas) -> None:
    unit = 6
    x = 26
    y = 23
    layers = [
        (6, 6, (24, 54, 151)),
        (4, 4, (42, 137, 68)),
        (2, 2, (224, 168, 36)),
        (0, 0, (201, 44, 44)),
    ]
    canvas.blend_rect(11, 9, 106, 88, (255, 255, 255), 0.07)
    canvas.blend_rect(15, 13, 98, 80, (0, 0, 0), 0.24)
    for ox, oy, color in layers:
        canvas.draw_digit_segments("6", x + ox, y + oy, unit, color)
        canvas.draw_digit_segments("4", x + 48 + ox, y + oy, unit, color)


def draw_checkers(canvas: Canvas) -> None:
    tile = 8
    y0 = 99
    for y in range(y0, SIZE):
        for x in range(0, SIZE, tile):
            color = (236, 236, 224) if ((x // tile) + (y // tile)) % 2 == 0 else (17, 24, 31)
            canvas.rect(x, y, tile, 1, color)


def render(output: Path) -> None:
    canvas = Canvas(SIZE, SIZE)
    canvas.fill_background()
    canvas.blend_rect(5, 5, SIZE - 10, SIZE - 10, (0, 0, 0), 0.26)
    canvas.blend_rect(9, 9, SIZE - 18, SIZE - 18, (255, 255, 255), 0.06)
    draw_icon_badge(canvas)
    canvas.draw_centered_text("VITA", 82, 2, (128, 204, 231), tracking=1)
    canvas.draw_centered_text("KART", 100, 2, (246, 242, 218), tracking=1)
    draw_checkers(canvas)
    canvas.write_png(output)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "livearea" / "icon0.png")
    args = parser.parse_args()
    output = args.output
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    render(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
