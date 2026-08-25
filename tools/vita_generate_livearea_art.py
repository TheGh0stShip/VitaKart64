#!/usr/bin/env python3
"""Generate deterministic Vita Kart 64 LiveArea/startup art.

This is local asset generation only. It does not build, install, launch,
connect to a Vita, harvest caches, pull crashes, or validate runtime behavior.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vita_generate_loading_art import Canvas  # noqa: E402


WIDTH = 280
HEIGHT = 158


def draw_small_checkers(canvas: Canvas) -> None:
    tile = 10
    y0 = HEIGHT - 34
    for y in range(y0, HEIGHT):
        for x in range(0, WIDTH, tile):
            xx = x // tile
            yy = y // tile
            color = (235, 236, 224) if (xx + yy) % 2 == 0 else (18, 25, 32)
            canvas.rect(x, y, tile, 1, color)


def draw_small_badge(canvas: Canvas) -> None:
    unit = 4
    x = 84
    y = 38
    layers = [
        (6, 6, (27, 61, 160)),
        (4, 4, (44, 145, 72)),
        (2, 2, (228, 172, 40)),
        (0, 0, (204, 45, 45)),
    ]
    canvas.blend_rect(56, 24, 168, 76, (255, 255, 255), 0.06)
    canvas.blend_rect(60, 28, 160, 68, (0, 0, 0), 0.22)
    for ox, oy, color in layers:
        canvas.draw_digit_segments("6", x + ox, y + oy, unit, color)
        canvas.draw_digit_segments("4", x + 42 + ox, y + oy, unit, color)


def render(output: Path) -> None:
    canvas = Canvas(WIDTH, HEIGHT)
    canvas.fill_background()
    canvas.blend_rect(10, 8, WIDTH - 20, HEIGHT - 16, (0, 0, 0), 0.24)
    canvas.blend_rect(16, 14, WIDTH - 32, HEIGHT - 28, (255, 255, 255), 0.06)
    draw_small_badge(canvas)
    canvas.draw_centered_text("VITA KART 64", 108, 3, (246, 242, 218), tracking=1)
    canvas.draw_centered_text("NATIVE VITA PORT", 132, 2, (128, 204, 231), tracking=1)
    draw_small_checkers(canvas)
    canvas.write_png(output)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "livearea" / "startup-vk64.png")
    args = parser.parse_args()
    output = args.output
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    render(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
