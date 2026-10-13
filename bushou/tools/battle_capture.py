"""Let the game draw any field-battle map, in Mesen (tools/mesen.py), and read the BG2 tilemap back.

Scenario 1, 織田信長: 軍事 -> 出陣 into 美濃 (province 22) with the first generals; the game reads the Mino
field map (ROM 0x381A6 = FIELD_MAPS + 154 * 22) at frame 6915 and has drawn it by ~7052. A savestate is
taken at frame 6880; for every map those 154 bytes are patched in PRG ROM and the state replayed (tools/replay.py),
so the game's own code draws it.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import BATTLE_H, FIELD_MAPS, FIELD_W

FIELD = 22                            # province whose field the game loads (美濃)
SAVE_AT, SHOT_AFTER = 6880, 180       # frames: savestate before the map is read / map on screen after it
TILEMAP = 0x0C00                      # BG2 tilemap (VRAM word address), 32 x 32 (left screen)
TERRAIN = 0xFC02                      # WRAM copy of the terrain the battle uses
BG2_CHR, CHR_BYTES = 0x4000, 0x8000   # BG2 tiles: VRAM word 0x4000 up
# title -> new game -> scenario 1 -> 織田信長 -> start; 軍事 -> 出陣 -> 美濃 -> generals -> confirm
INPUTS = ("w900 start:10 w300 a:10 w200 a:10 w200 a:10 w200 a:10 w200 up:10 w60 a:10 w200 a:10 w200 a:10 w200 "
          "a:10 w300 a:10 w900 right:10 w30 a:10 w100 down:10 w30 down:10 w30 a:10 w100 up:10 w30 a:10 w100 "
          "a:10 w100 down:10 w30 a:10 w100 b:10 w100 a:10 w100 a:10 w100 a:10 w100 b:10 w100 a:10 w100 a:10 w200 "
          "a:10 w200 a:10 w300 a:10 w300")
SIZE = FIELD_W * BATTLE_H


def capture_fields(rom_path: str, maps: list[bytes], chr_and_palette: bool = True) -> list[dict]:
    """Per map: terrain bytes the battle uses (WRAM), BG2 tilemap (32 x 32 entries) and, for the first map,
    the BG2 CHR (VRAM bytes 0x8000-0xFFFF) and CGRAM."""
    at = FIELD_MAPS + SIZE * FIELD
    runs = []
    for k, m in enumerate(maps):
        read = [("wram", TERRAIN, SIZE), ("vram", 2 * TILEMAP, 2048)]
        if k == 0 and chr_and_palette:
            read += [("vram", 2 * BG2_CHR, CHR_BYTES), ("cgram", 0, 512)]
        runs.append({"patch": [(at, bytes(m))], "shot": SHOT_AFTER, "read": read})
    out = []
    for res in replay(rom_path, INPUTS, SAVE_AT, runs):
        tm = res[1]
        d = {"terrain": res[0], "tilemap": [tm[2 * i] | tm[2 * i + 1] << 8 for i in range(1024)]}
        if len(res) > 2:
            d["chr"], d["cgram"] = res[2], res[3]
        out.append(d)
    return out
