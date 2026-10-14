#!/usr/bin/env python3
"""Check the battle field decoding (rom.Rom.battle_tilemap, battle_chr, battle_palettes) against the game (needs
Mesen 2, about 2 minutes).

The opening battle of 桶狭間 (tools/sequences.TO_INFO) is fought on field 6: the event code at $C9:14F3 does
LDA #$06 / STA $7E7F82, and $C6:F885 loads LZ entry 347 + $7F82 through the pointer table $C1:F6BA. A savestate
is taken after the event has set $7F82 but before the field is loaded (frame 13898; the load is at frame 13975);
run f writes f to $7E:7F82 there, so the game's own code looks up and draws field f. When the battle is on screen:
1. the BG tilemap at VRAM 0xF000 (rows 0-13, columns 0-30) must equal rom.Rom.battle_tilemap(f), and $7E:7F82
   must be f;
2. the BG characters VRAM 0x8400-0xD000 must equal rom.Rom.battle_chr(), CGRAM palettes 2 and 7 the ROM
   palettes (both the same in every run).

Usage: .venv/bin/python taikou/verify_battle_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import BATTLE_COUNT, BATTLE_H, BATTLE_PALETTES, BATTLE_W, DEFAULT_ROM, Rom, le16
from sequences import TO_INFO, split_at

BOOT, SAVE_AT, STEPS = split_at(TO_INFO, 13900)
SHOT = 1550                  # frame 15448: the battle field is on screen
FIELD_VAR = 0x7F82           # $7E:7F82
CHR_LO, CHR_HI = 0x8400, 0xD000


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場（合戰）地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    read = [("wram", FIELD_VAR, 1), ("vram", 0xF000, 2 * 32 * BATTLE_H), ("vram", CHR_LO, CHR_HI - CHR_LO),
            ("cgram", 0, 256)]
    runs = [{"steps": STEPS, "shot": SHOT, "read": read}]
    runs += [{"wram": [(FIELD_VAR, bytes([f]))], "steps": STEPS, "shot": SHOT, "read": read}
             for f in range(BATTLE_COUNT)]
    shots = replay(args.rom, BOOT, SAVE_AT, runs)
    errors = 0

    field, *_ = shots[0]
    ok = field[0] == 6
    print(f"[unpatched] $7E:7F82 = {field[0]} ({'==' if ok else '!='} 6, 桶狭間)")
    errors += not ok
    good, bad = [], []
    for f, (var, tm, _, _) in enumerate(shots[1:]):
        want = rom.battle_tilemap(f)
        got = [[le16(tm, 2 * (32 * y + x)) for x in range(BATTLE_W)] for y in range(BATTLE_H)]
        (good if var[0] == f and got == want else bad).append(f)
    print(f"[fields] {len(good)}/{BATTLE_COUNT} fields: $7F82 = f and VRAM 0xF000 31 x 14 == battle_tilemap(f)"
          + (f" (NG {bad})" if bad else ""))
    errors += len(bad)
    chr_want = rom.battle_chr()[CHR_LO:CHR_HI]
    n = sum(s[2] == chr_want for s in shots)
    print(f"[chr] VRAM {CHR_LO:#x}-{CHR_HI:#x} == battle_chr() in {n}/{len(shots)} runs")
    errors += n != len(shots)
    pals = rom.battle_palettes()
    n = sum(all([le16(s[3], 32 * p + 2 * i) for i in range(16)] == pal for p, pal in pals.items()) for s in shots)
    print(f"[palettes] CGRAM palettes {sorted(BATTLE_PALETTES)} == ROM in {n}/{len(shots)} runs")
    errors += n != len(shots)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
