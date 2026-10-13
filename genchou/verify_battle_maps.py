#!/usr/bin/env python3
"""Check the battle maps (rom.Rom.battle_values / battle_tileset / battle_palette) against the game (needs
Mesen 2, about 1 minute).

Scenario 1 is played (savestate replay, tools/replay.py) up to the press that starts an expedition from
オノン河流域 to ゴルゴナク河原 (軍事 → 遠征, the rest with the defaults). The three loaders the battle runs read
the target country with `LDY #4; LDA ($00),y`: $C7:92F4 (map record, LZ entry 136 + country (+ 14 in the world
scenarios, flag $7E:5425)), $C7:9395 (tile set, LZ entry 229 + k) and $C7:9527 (palette 0x20 + 2k); for every map
n the three are patched to `LDA #country` and $7E:5425 is set to 0 (Mongolia) or 1 (world). On the battle
screen BG2 is read back: the tilemap (VRAM 0xF000) at columns 2-29, rows 3-23 must be palette 6, tile 0x40 + v
for the record's 28x21 values v, the tiles at VRAM 0x4800 must equal the tile set's LZ entry, and CGRAM palette 6
must be battle_palette(k) or the next palette of the block (the two alternate, colours 13-14).

Usage: .venv/bin/python genchou/verify_battle_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import presses, replay
from rom import (
    BATTLE_COUNT,
    BATTLE_PALETTE0,
    BATTLE_TILE_H,
    BATTLE_TILE_W,
    BATTLE_TILESET_ENTRY,
    DEFAULT_ROM,
    MONGOL_COUNTRIES,
    PALETTE_BLOCK,
    Rom,
)

# scenario 1, first turn: 軍事 (down x3, a), 遠征 yes, the map cursor on ゴルゴナク河原, 総指揮 yes, 編成 no, then
# the defaults up to "遠征を開始してよろしいですか"; the save is taken just before that press
BOOT = ("w2100 start:30 w100 start:4 w300 a:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w200 "
        "a:10 w200 a:10 w300 a:10 w300 a:10 w300 a:10 w300 down:10 w30 down:10 w30 down:10 w30 a:10 w200 a:10 w200 "
        "a:10 w60 w60 down:4 w30 down:4 w30 left:4 w30 a:10 w100 a:10 w150 down:4 w30 a:10 w150 a:10 w150 "
        "a:10 w150 a:10 w150 a:10 w150 a:10 w150 a:10 w150 a:10 w150 a:10 w300")
STEPS = "a:10 w300 a:10 w300 a:10 w300"
SHOT = 990
COUNTRY_LOADS = [0x792F4, 0x79395, 0x79527]   # LDY #$0004; LDA ($00),y -> LDA #country; NOP NOP
WORLD_FLAG = 0x5425
TILEMAP, ROW0, COL0, TILE0, PALETTE = 0xF000, 3, 2, 0x40, 6
TILES = 0x4000 + 32 * TILE0


def save_frame(steps: str) -> int:
    last = presses(steps, 10)[-1]
    return last[0] + last[2] + 20 + int(steps.split()[-1][1:])


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = []
    for n in range(BATTLE_COUNT):
        world = n >= MONGOL_COUNTRIES
        country = n - MONGOL_COUNTRIES if world else n
        tiles = len(rom.entry(BATTLE_TILESET_ENTRY + rom.battle_tileset(n)))
        runs.append({"patch": [(o, bytes([0xA9, country, 0, 0xEA, 0xEA])) for o in COUNTRY_LOADS],
                     "wram": [(WORLD_FLAG, bytes([world]))], "steps": STEPS, "shot": SHOT,
                     "read": [("vram", TILEMAP, 0x800), ("vram", TILES, tiles), ("cgram", 32 * PALETTE, 32)]})
    shots = replay(args.rom, BOOT, save_frame(BOOT), runs)
    bad, sets = [], {}
    for n, (tmap, tiles, cgram) in enumerate(shots):
        k = rom.battle_tileset(n)
        sets.setdefault(k, []).append(n)
        values = rom.battle_values(n)
        cells = sum((tmap[2 * (32 * (ROW0 + r) + COL0 + c)] | tmap[2 * (32 * (ROW0 + r) + COL0 + c) + 1] << 8)
                    == (PALETTE << 10 | TILE0 + values[BATTLE_TILE_W * r + c])
                    for r in range(BATTLE_TILE_H) for c in range(BATTLE_TILE_W))
        pals = [rom.data[PALETTE_BLOCK + 32 * p:PALETTE_BLOCK + 32 * p + 32]
                for p in (BATTLE_PALETTE0 + 2 * k, BATTLE_PALETTE0 + 2 * k + 1)]
        ok_tiles = tiles == rom.entry(BATTLE_TILESET_ENTRY + k)
        if cells != len(values) or not ok_tiles or cgram not in pals:
            bad.append(f"map {n}: tilemap {cells}/{len(values)}, tiles {ok_tiles}, palette {cgram in pals}")
    print(f"[battle maps] {BATTLE_COUNT - len(bad)}/{BATTLE_COUNT}: BG2 tilemap 28x21 = 0x40 + record values "
          f"(palette 6), tiles = LZ {BATTLE_TILESET_ENTRY} + tile set, CGRAM palette 6 = palette 0x20 + 2 tile set")
    print("[battle maps] tile sets: " + ", ".join(f"{k} (LZ {BATTLE_TILESET_ENTRY + k}): {len(v)} maps"
                                                 for k, v in sorted(sets.items())))
    for b in bad:
        print("  NG", b)
    print(f"{'ALL OK' if not bad else f'{len(bad)} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
