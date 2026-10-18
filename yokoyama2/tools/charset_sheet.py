#!/usr/bin/env python3
"""Font check sheet: every code 0x100-0x5FF with its ROM glyph and the character of data/charset.txt
(output/charset_sheet.png), to check the human reading of the glyphs.

Usage: .venv/bin/python yokoyama2/tools/charset_sheet.py [--rom ROM] [--out DIR]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from rom import DEFAULT_ROM, FONT16_COUNT, Rom

LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
SCALE = 3
FIRST, LAST = 0x100, 0x200 + FONT16_COUNT


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
    cw, ch = 16 * SCALE + 34, 16 * SCALE + 16
    im = Image.new("RGB", (16 * cw, (LAST - FIRST) // 16 * ch), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    for c in range(FIRST, LAST):
        i = c - FIRST
        x0, y0 = i % 16 * cw, i // 16 * ch
        rows = rom.glyph8(c) if c < 0x200 else rom.glyph16(c)
        for y, row in enumerate(rows):
            for x, v in enumerate(row):
                if v:
                    px, py = x0 + x * SCALE, y0 + 12 + y * SCALE
                    dr.rectangle([px, py, px + SCALE - 1, py + SCALE - 1], fill=(0, 0, 0))
        dr.text((x0, y0), f"{c:03X}", fill=(160, 0, 0), font=small)
        dr.text((x0 + 16 * SCALE + 4, y0 + 18), rom.char(c), fill=(0, 0, 200), font=font)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "charset_sheet.png")
    im.save(path)
    print(path)


if __name__ == "__main__":
    main()
