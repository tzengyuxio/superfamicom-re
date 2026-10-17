#!/usr/bin/env python3
"""Font check sheets: every dialogue code 01-D4 with its ROM glyph and the character of data/charset.txt
(output/charset_sheet.png), and every 16x16 glyph of the yaku screen with data/glyph16.txt (output/glyph16_sheet.png).

Usage: .venv/bin/python mahjong2/tools/charset_sheet.py [--rom ROM] [--out DIR]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from rom import DEFAULT_ROM, FONT_CODES, GLYPH16_COUNT, Rom, decode_tile

LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
SCALE = 3


def main() -> None:
    ap = argparse.ArgumentParser(description="字型核對圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    try:
        font = ImageFont.truetype(LABEL_FONT, 16 * SCALE // 2)
        small = ImageFont.truetype(LABEL_FONT, 9)
    except OSError:
        font = small = ImageFont.load_default()
    cw, ch = 8 * SCALE + 34, 16 * SCALE + 16
    im = Image.new("RGB", (16 * cw, (FONT_CODES + 16) // 16 * ch), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for c in range(1, FONT_CODES + 1):
        x0, y0 = c % 16 * cw, c // 16 * ch
        g = rom.glyph(c)
        for half in range(2):
            for i, v in enumerate(decode_tile(g[32 * half:32 * half + 32])):
                if v & 2:  # ink is colour 2/3 (plane 1); colour 1 is the window background
                    x, y = x0 + i % 8 * SCALE, y0 + 12 + (half * 8 + i // 8) * SCALE
                    dr.rectangle([x, y, x + SCALE - 1, y + SCALE - 1], fill=(0, 0, 0))
        dr.text((x0, y0), f"{c:02X}", fill=(160, 0, 0), font=small)
        dr.text((x0 + 8 * SCALE + 4, y0 + 18), rom.char(c), fill=(0, 0, 200), font=font)
    os.makedirs(args.out, exist_ok=True)
    im.save(os.path.join(args.out, "charset_sheet.png"))

    cw, ch = 16 * SCALE + 40, 16 * SCALE + 16
    im = Image.new("RGB", (16 * cw, (GLYPH16_COUNT + 15) // 16 * ch), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for g in range(GLYPH16_COUNT):
        x0, y0 = g % 16 * cw, g // 16 * ch
        raw = rom.glyph16(g)
        for q in range(4):
            for i, v in enumerate(decode_tile(raw[32 * q:32 * q + 32])):
                if v == 3:  # ink
                    x, y = x0 + (q % 2 * 8 + i % 8) * SCALE, y0 + 12 + (q // 2 * 8 + i // 8) * SCALE
                    dr.rectangle([x, y, x + SCALE - 1, y + SCALE - 1], fill=(0, 0, 0))
        dr.text((x0, y0), f"{g:02X}", fill=(160, 0, 0), font=small)
        dr.text((x0 + 16 * SCALE + 4, y0 + 18), rom.glyphs16[g], fill=(0, 0, 200), font=font)
    im.save(os.path.join(args.out, "glyph16_sheet.png"))
    print(args.out)


if __name__ == "__main__":
    main()
