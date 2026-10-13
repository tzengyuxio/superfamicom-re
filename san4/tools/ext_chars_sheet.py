#!/usr/bin/env python3
"""Sheet of the game's user-area characters (Shift-JIS 0xEB9F-0xEBFC): ROM glyph, code and the character
rom.EXT_CHARS assigns, for checking the assignments by eye.

Usage: .venv/bin/python san4/tools/ext_chars_sheet.py [--rom ROM] [--out PNG]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from rom import DEFAULT_ROM, EXT_CHARS, Rom

FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"


def main() -> None:
    ap = argparse.ArgumentParser(description="外字對照圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "output", "ext_chars.png"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    codes = rom.glyph_codes()
    ext = [(g, c) for g, c in enumerate(codes) if 0xEB9F <= c <= 0xEBFC]
    try:
        font = ImageFont.truetype(FONT, 32)
        small = ImageFont.truetype(FONT, 12)
    except OSError:
        font = small = ImageFont.load_default()
    cols, cw, chh = 8, 110, 50
    im = Image.new("RGB", (cols * cw, (len(ext) + cols - 1) // cols * chh), "white")
    dr = ImageDraw.Draw(im)
    for i, (g, c) in enumerate(ext):
        x, y = i % cols * cw, i // cols * chh
        for gy, row in enumerate(rom.glyph(g)):
            for gx, v in enumerate(row):
                if v:
                    dr.rectangle([x + 4 + 2 * gx, y + 4 + 2 * gy, x + 5 + 2 * gx, y + 5 + 2 * gy], fill="black")
        dr.text((x + 40, y + 2), EXT_CHARS.get(c, "?"), fill="blue", font=font)
        dr.text((x + 76, y + 30), f"{c:04X}", fill="gray", font=small)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    im.save(args.out)
    print(f"{len(ext)} 個外字 → {args.out}")


if __name__ == "__main__":
    main()
