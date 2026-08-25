#!/usr/bin/env python3
"""Generate the Vita Kart 64 static loading-card PNG.

The output is deterministic and uses only the Python standard library. It does
not build, install, launch, connect to a Vita, or validate runtime behavior.
"""

from __future__ import annotations

import argparse
import math
import struct
import zlib
from pathlib import Path


WIDTH = 960
HEIGHT = 544


FONT = {
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "0": ["11111", "10001", "10011", "10101", "11001", "10001", "11111"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["11110", "00001", "00001", "11110", "10000", "10000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["10010", "10010", "10010", "11111", "00010", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01111", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "11110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
}


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


class Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(width * height * 3)

    def fill_background(self) -> None:
        cx = self.width * 0.5
        cy = self.height * 0.42
        for y in range(self.height):
            for x in range(self.width):
                dx = (x - cx) / self.width
                dy = (y - cy) / self.height
                radial = max(0.0, 1.0 - math.sqrt(dx * dx * 5.0 + dy * dy * 7.0))
                stripe = 10 if ((x + y * 2) // 38) % 2 == 0 else 0
                r = int(10 + radial * 30 + stripe)
                g = int(18 + radial * 36 + stripe)
                b = int(26 + radial * 44 + stripe)
                self.set_pixel(x, y, (r, g, b))

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        offset = (y * self.width + x) * 3
        self.pixels[offset : offset + 3] = bytes(color)

    def blend_pixel(self, x: int, y: int, color: tuple[int, int, int], alpha: float) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        offset = (y * self.width + x) * 3
        inv = 1.0 - alpha
        self.pixels[offset] = int(self.pixels[offset] * inv + color[0] * alpha)
        self.pixels[offset + 1] = int(self.pixels[offset + 1] * inv + color[1] * alpha)
        self.pixels[offset + 2] = int(self.pixels[offset + 2] * inv + color[2] * alpha)

    def rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        for yy in range(max(0, y), min(self.height, y + h)):
            row = (yy * self.width + max(0, x)) * 3
            for _xx in range(max(0, x), min(self.width, x + w)):
                self.pixels[row : row + 3] = bytes(color)
                row += 3

    def blend_rect(self, x: int, y: int, w: int, h: int, color: tuple[int, int, int], alpha: float) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.blend_pixel(xx, yy, color, alpha)

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        scale: int,
        color: tuple[int, int, int],
        tracking: int = 1,
    ) -> None:
        cursor = x
        for char in text.upper():
            glyph = FONT.get(char, FONT[" "])
            for gy, row in enumerate(glyph):
                for gx, enabled in enumerate(row):
                    if enabled == "1":
                        self.rect(cursor + gx * scale, y + gy * scale, scale, scale, color)
            cursor += (5 + tracking) * scale

    def text_width(self, text: str, scale: int, tracking: int = 1) -> int:
        if not text:
            return 0
        return len(text) * 5 * scale + max(0, len(text) - 1) * tracking * scale

    def draw_centered_text(
        self,
        text: str,
        y: int,
        scale: int,
        color: tuple[int, int, int],
        tracking: int = 1,
        shadow: bool = True,
    ) -> None:
        x = (self.width - self.text_width(text, scale, tracking)) // 2
        if shadow:
            self.draw_text(text, x + scale, y + scale, scale, (0, 0, 0), tracking)
        self.draw_text(text, x, y, scale, color, tracking)

    def draw_digit_segments(self, digit: str, x: int, y: int, unit: int, color: tuple[int, int, int]) -> None:
        maps = {
            "4": ("b", "c", "f", "g"),
            "6": ("a", "c", "d", "e", "f", "g"),
        }
        segments = set(maps[digit])
        thick = unit
        length = unit * 5
        if "a" in segments:
            self.rect(x + thick, y, length, thick, color)
        if "b" in segments:
            self.rect(x + length + thick, y + thick, thick, length, color)
        if "c" in segments:
            self.rect(x + length + thick, y + length + thick * 2, thick, length, color)
        if "d" in segments:
            self.rect(x + thick, y + length * 2 + thick * 2, length, thick, color)
        if "e" in segments:
            self.rect(x, y + length + thick * 2, thick, length, color)
        if "f" in segments:
            self.rect(x, y + thick, thick, length, color)
        if "g" in segments:
            self.rect(x + thick, y + length + thick, length, thick, color)

    def write_png(self, output: Path) -> None:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            start = y * stride
            raw.extend(self.pixels[start : start + stride])
        payload = (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
            + png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + png_chunk(b"IEND", b"")
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)


def draw_checkered(canvas: Canvas) -> None:
    tile = 24
    y0 = HEIGHT - 86
    canvas.blend_rect(0, y0 - 16, WIDTH, 6, (255, 255, 255), 0.32)
    for y in range(y0, HEIGHT):
        for x in range(0, WIDTH, tile):
            yy = y // tile
            xx = x // tile
            color = (235, 236, 224) if (xx + yy) % 2 == 0 else (22, 30, 38)
            canvas.rect(x, y, tile, 1, color)


def draw_badge(canvas: Canvas) -> None:
    start_x = 300
    start_y = 126
    unit = 18
    offsets = [
        (20, 20, (25, 57, 156)),
        (14, 14, (43, 139, 68)),
        (8, 8, (225, 169, 37)),
        (0, 0, (201, 44, 44)),
    ]
    canvas.blend_rect(256, 92, 448, 248, (255, 255, 255), 0.06)
    canvas.blend_rect(264, 100, 432, 232, (0, 0, 0), 0.28)
    for ox, oy, color in offsets:
        canvas.draw_digit_segments("6", start_x + ox, start_y + oy, unit, color)
        canvas.draw_digit_segments("4", start_x + 164 + ox, start_y + oy, unit, color)
    canvas.blend_rect(start_x - 16, start_y - 20, 384, 6, (255, 255, 255), 0.35)
    canvas.blend_rect(start_x - 16, start_y + 188, 384, 6, (255, 255, 255), 0.18)


def render(output: Path) -> None:
    canvas = Canvas(WIDTH, HEIGHT)
    canvas.fill_background()
    canvas.blend_rect(44, 40, WIDTH - 88, HEIGHT - 80, (0, 0, 0), 0.28)
    canvas.blend_rect(56, 52, WIDTH - 112, HEIGHT - 104, (255, 255, 255), 0.06)
    draw_badge(canvas)
    canvas.draw_centered_text("VITA KART 64", 360, 8, (246, 242, 218), tracking=2)
    canvas.draw_centered_text("NATIVE PS VITA PORT", 418, 4, (128, 204, 231), tracking=2)
    canvas.draw_centered_text("PRELOADING TEXTURES SHADERS AUDIO", 454, 3, (231, 197, 84), tracking=1)
    canvas.draw_centered_text("FIRST RUN MAY TAKE LONGER", 484, 3, (172, 187, 198), tracking=1)
    draw_checkered(canvas)
    canvas.write_png(output)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "assets" / "vita" / "loading.png")
    args = parser.parse_args()
    output = args.output
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    render(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
