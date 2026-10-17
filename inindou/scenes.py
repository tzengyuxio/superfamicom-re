"""Button scripts and a screen reader shared by the Mesen verification scripts (tools/replay.py syntax).

BOOT starts a new game: title, story pages, the naming screen (types あ, moves to 決定, YES) and waits on the
first map (伊賀の里). The savestate is taken right after it. Presses are held 6 frames in menus: a hold of 10
or more repeats and moves the cursor one more line.
The status screens: field menu -> 情報 (4 down) -> 人物選択 -> the first party member -> 能力 / 道具 / 術.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame
from rom import FONT, GLYPH_COUNT

BOOT = "w1500 start:10 w200 a:10 w200 a:10 w200 a:10 w60 a w60 up w40 left w40 a w200 a w400"
SAVE = end_frame(BOOT)
MENU = "a:6 w60 down:6 w40 down:6 w40 down:6 w40 down:6 w40 a:6 w100 a:6 w100 "
ABILITY = MENU + "a:6 w500"
ITEMS = MENU + "down:6 w40 a:6 w300"
SPELLS = MENU + "down:6 w40 down:6 w40 a:6 w300"

# Window layer: BG1, tilemap VRAM byte 0, 4bpp tiles from VRAM byte 0x8000; text in colour 15
TILEMAP, TILEMAP_SIZE = 0x0000, 0x800
WINDOW_CHR, WINDOW_CHR_SIZE = 0x8000, 0x4000
STATE_WRAM = 0xF0B8                      # first person state record ($7E:EFF0 + 0xC8)
BAG_WRAM = 0xEFF0 + 0x38


class ScreenReader:
    """Matches the window layer's 8x8 tiles (colour 15 = ink) against the ROM font: 2x2 tiles = a 16x16 glyph,
    1x2 tiles = a half-width 8x16 glyph (h = 2..11 are digits 0-9)."""

    def __init__(self, rom_data: bytes):
        self.full, self.half = {}, {}
        for g in range(15, GLYPH_COUNT):
            self.full.setdefault(rom_data[FONT + 32 * g:FONT + 32 * g + 32], g)
        for h in range(30):
            self.half.setdefault(rom_data[FONT + 16 * h:FONT + 16 * h + 16], h)

    def lines(self, tilemap: bytes, chr_: bytes) -> dict[int, list]:
        """Screen row -> tokens: glyph numbers (int) and half-width numbers ('h<n>')."""
        def bits(t: int) -> bytes:
            o, out = 32 * t, []
            for y in range(8):
                b = 0
                for x in range(8):
                    c = 0
                    for p in range(4):
                        c |= (chr_[o + (p // 2) * 16 + 2 * y + (p % 2)] >> (7 - x) & 1) << p
                    b = b << 1 | (c == 15)
                out.append(b)
            return bytes(out)

        def tile(x: int, y: int) -> int:
            i = 2 * (y * 32 + x)
            return (tilemap[i] | tilemap[i + 1] << 8) & 0x3FF

        rows = {}
        for y in range(27):
            toks, x = [], 0
            while x < 32:
                if x < 31:
                    g = bits(tile(x, y)) + bits(tile(x + 1, y)) + bits(tile(x, y + 1)) + bits(tile(x + 1, y + 1))
                    if g in self.full:
                        toks.append(self.full[g])
                        x += 2
                        continue
                h = bits(tile(x, y)) + bits(tile(x, y + 1))
                if h in self.half and any(h):
                    toks.append(f"h{self.half[h]}")
                x += 1
            if toks:
                rows[y] = toks
        return rows


def numbers(tokens: list) -> list[int]:
    """Runs of half-width digits in a token list."""
    s = "".join(str(int(t[1:]) - 2) if isinstance(t, str) and 2 <= int(t[1:]) <= 11 else " " for t in tokens)
    return [int(m) for m in re.findall(r"\d+", s)]
