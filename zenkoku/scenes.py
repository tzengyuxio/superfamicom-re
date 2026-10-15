"""Button sequences (tools/drive.py syntax) and screen readers shared by the verify_*.py scripts.

Timings were measured with tools/drive.py; presses are held 10 frames (shorter presses are often missed).
A = はい, B = いいえ.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import presses
from rom import FONT, GLYPH_COUNT, HALF_DIGIT0, HALF_FONT

# Power-on -> title -> start -> 新しく始める -> scenario list (cursor on 1:列強争覇の章), about frame 3700
MENU = "w3000 start:10 w200 a:10 w200 a:10 w200"


def scenario(s: int) -> str:
    """Scenario list -> scenario s (0-3); the scenario is loaded and the map painted within 600 frames."""
    return " ".join(["down:10 w30"] * s + ["a:10 w600"])


# Scenario 1, コンピュータどうしの戦いを見ますか Y, 方言 N, 0 players, computer strength 1, 全てよろしいですか Y:
# the computers play; in the savestate replay the first battle is 美濃 (17-mode province 8), about 2940 frames on.
CPU_GAME_17 = MENU + " a:10 w400 a:10 w150 b:10 w150 a:10 w300 a:10 w300 a:10 w300"

# Scenario 2, one player, 織田信長 (slot 24): コンピュータ戦 N, 方言 N, players up to 1, 担当 (cursor on 尾張), 尾張の
# 織田信長ですね Y, 姓名変更 N, ability roll and confirmations -> first command screen (1560年春)
TO_COMMAND = (MENU + " down:10 w30 a:10 w400 b:10 w150 b:10 w150 up:10 w30 a:10 w150 a:10 w300 a:10 w200 "
              "b:10 w200 " + " ".join(["a:10 w60"] * 5) + " a:10 w300 a:10 w200 a:10 w200 a:10 w2700")
# Command screen -> その他 -> 情報 -> 国 -> "どの国をご覧になりますか" (cursor on 尾張); a then shows the province
TO_INFO = TO_COMMAND + (" a:10 w100 right:10 w60 right:10 w60 right:10 w60 a:10 w100 down:10 w30 down:10 w30 "
                        "a:10 w150")
# Command screen -> 軍事 -> 戦争 -> 美濃 -> soldiers -> confirm: the battle map is drawn on the last press
TO_WAR = TO_COMMAND + (" a:10 w100 a:10 w100 left:10 w60 right:10 w60 right:10 w60 a:10 w100 left:10 w30 up:10 "
                       "w30 a:10 w100 a:10 w100 a:10 w100 a:10 w100")


def save_frame(steps: str) -> int:
    """First frame after the last press of steps and its wait, as tools/replay.py counts them."""
    last = presses(steps, 10)[-1]
    return last[0] + last[2] + 20 + int(steps.split()[-1][1:])


def length(steps: str) -> int:
    """Frames the steps take (a press is its hold + 20 frames)."""
    n = 0
    for st in steps.split():
        if st.startswith("w"):
            n += int(st[1:])
        else:
            n += int(st.partition(":")[2] or 4) + 20
    return n


# ---------------------------------------------------------------- BG3 text reader
TEXT_TILEMAP, TEXT_CHR = 0xF800, 0x0000   # BG3: 32 x 32 tilemap, 2bpp characters


class Screen:
    """BG3 text of a VRAM dump, read by exact comparison of the drawn tiles with the ROM fonts.

    A full-width glyph is 2 x 2 tiles (font order TL TR BL BR); a half-width one is 1 x 2 tiles."""

    def __init__(self, rom, vram: bytes):
        self.vram = vram
        self.kanji = {}
        for g in range(GLYPH_COUNT):
            raw = rom.data[FONT + 32 * g:FONT + 32 * g + 32]
            self.kanji.setdefault((raw[0:8], raw[8:16], raw[16:24], raw[24:32]), g)
        self.half = {}
        for k in range(200):
            self.half.setdefault(rom.data[HALF_FONT + 16 * k:HALF_FONT + 16 * k + 16], k)

    def tile(self, tx: int, ty: int) -> bytes:
        o = TEXT_TILEMAP + 2 * (ty * 32 + tx)
        t = (self.vram[o] | self.vram[o + 1] << 8) & 0x3FF
        c = TEXT_CHR + 16 * t
        return bytes(self.vram[c + 2 * y] | self.vram[c + 2 * y + 1] for y in range(8))

    def glyphs(self, tx: int, ty: int, n: int, stop_blank: bool = True) -> list[int]:
        """Up to n full-width glyph numbers from tile (tx, ty) rightwards (stops at the first non-glyph, and at
        the first blank glyph 0 if stop_blank)."""
        out = []
        for i in range(n):
            x = tx + 2 * i
            k = (self.tile(x, ty), self.tile(x + 1, ty), self.tile(x, ty + 1), self.tile(x + 1, ty + 1))
            if k not in self.kanji or stop_blank and self.kanji[k] == 0:
                break
            out.append(self.kanji[k])
        return out

    def number(self, tx: int, ty: int, width: int) -> int | None:
        """A right-aligned half-width number in tiles tx .. tx + width - 1 (None if a cell is not a digit or blank)."""
        s = ""
        for x in range(tx, tx + width):
            k = self.half.get(self.tile(x, ty) + self.tile(x, ty + 1))
            if k is not None and HALF_DIGIT0 <= k < HALF_DIGIT0 + 10:
                s += str(k - HALF_DIGIT0)
            elif not any(self.tile(x, ty) + self.tile(x, ty + 1)):
                if s:
                    return None
            else:
                return None
        return int(s) if s else None
