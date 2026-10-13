#!/usr/bin/env python3
"""Check data/charset.txt by eye: every font glyph from the ROM (black) next to its charset character (blue).

The glyphs are the game's own font (rom.Rom.glyph), so a wrong assignment shows as a pair that differs.

Usage: .venv/bin/python san3/tools/charset_sheet.py [--rom ROM] [--out san3/output/charset_sheet.png]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from rom import DEFAULT_ROM, GLYPH_COUNT, Rom

FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
COLS, SCALE, CELL_W, CELL_H = 16, 3, 110, 64


def main() -> None:
    ap = argparse.ArgumentParser(description="字型對照圖：ROM 字形 vs charset.txt")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--font", default=FONT, help="畫指定字用的系統字型")
    ap.add_argument("--out", default=os.path.join(HERE, "output", "charset_sheet.png"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    font, small = ImageFont.truetype(args.font, 40), ImageFont.truetype(args.font, 12)
    im = Image.new("RGB", (COLS * CELL_W, (GLYPH_COUNT + COLS - 1) // COLS * CELL_H), "white")
    draw = ImageDraw.Draw(im)
    for g in range(GLYPH_COUNT):
        x0, y0 = g % COLS * CELL_W + 4, g // COLS * CELL_H + 4
        for y, row in enumerate(rom.glyph(g)):
            for x, v in enumerate(row):
                if v:
                    draw.rectangle([x0 + x * SCALE, y0 + y * SCALE, x0 + x * SCALE + SCALE - 1,
                                    y0 + y * SCALE + SCALE - 1], fill="black")
        draw.text((x0 + 52, y0), rom.charset[g], font=font, fill="blue")
        draw.text((x0, y0 + 48), f"{g} {0x8140 + g:04X}", font=small, fill="gray")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    im.save(args.out)
    print(f"{GLYPH_COUNT} glyphs → {args.out}")


if __name__ == "__main__":
    main()
