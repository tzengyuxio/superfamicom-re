#!/usr/bin/env python3
"""Check the scenario blocks (rom.Rom.block_a / block_b, FAMILY, region names and positions) against the game
(needs Mesen 2, about 30 seconds).

The game is started in Mesen (tools/mesen.py, savestate replay tools/replay.py) up to the scenario menu;
for each scenario the WRAM areas the loader $C4:400F fills are cleared, the scenario is chosen and the areas are
read back: $7E:37F7 (block A as Rom.loaded_a gives it: persons, countries, houses), $7E:4F38 (block B: women ...), $7E:4C94 (family),
$7E:2000 (region names) and $7E:545C (region label positions). The 4th scenario is not in the menu (the game
loads it with $C4:400F(3) when scenario 1's Mongolia is unified, $C4:1C78); it is checked by patching the menu
code at $C4:2B4F to pass 3. The persons, countries, houses and women decoded from WRAM must equal the ROM's.

Usage: .venv/bin/python genchou/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    A_SIZE,
    A_WRAM,
    B_SIZE,
    B_WRAM,
    DEFAULT_ROM,
    FAMILY,
    REGION_NAMES,
    REGION_POS,
    SCENARIO_A,
    SCENARIO_B,
    SCENARIO_COUNT,
    Rom,
)

# title (START twice) -> どちらを行いますか: 新しくゲームを始める (a) -> scenario menu, cursor on 1
BOOT = "w2100 start:30 w100 start:4 w300 a:10 w200 a:10 w200"
SAVE_AT = 3044
SHOT = 400
MENU_ARG = 0x42B4F                         # $C4:2B4F: LDA $03,s; AND #$00FF (menu choice) -> LDA #$0003; NOP NOP
FAMILY_WRAM, FAMILY_SIZE = 0x4C94, 0x2A4
NAMES_WRAM, NAMES_SIZE = 0x2000, 0x210
POS_WRAM, POS_SIZE = 0x545C, 0x42


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（人物、國、王家、女性）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    areas = [(A_WRAM, A_SIZE), (B_WRAM, B_SIZE), (FAMILY_WRAM, FAMILY_SIZE), (NAMES_WRAM, NAMES_SIZE),
             (POS_WRAM, POS_SIZE)]
    clear = [(a, bytes(n)) for a, n in areas]
    runs = []
    for sc in range(SCENARIO_COUNT):
        menu = min(sc, 2)
        patch = [(MENU_ARG, bytes.fromhex("a90300eaea"))] if sc == 3 else []
        runs.append({"patch": patch, "wram": clear, "steps": "down:10 w30 " * menu + "a:10",
                     "shot": SHOT, "read": [("wram", a, n) for a, n in areas]})
    shots = replay(args.rom, BOOT, SAVE_AT, runs)
    errors = 0
    for sc, (wa, wb, wf, wn, wp) in enumerate(shots):
        world = sc > 0
        want = {"block A": rom.loaded_a(sc), "block B": rom.block_b(sc),
                "family": rom.data[FAMILY:FAMILY + FAMILY_SIZE],
                "region names": rom.data[REGION_NAMES["world" if world else "mongol"]:][:NAMES_SIZE],
                "region positions": rom.data[REGION_POS["world" if world else "mongol"]:][:POS_SIZE]}
        got = dict(zip(want, (wa, wb, wf, wn, wp)))
        src = {"block A": f"${rom.ptr(SCENARIO_A + 3 * sc) | 0xC00000:06X}",
               "block B": f"${rom.ptr(SCENARIO_B + 3 * sc) | 0xC00000:06X}"}
        line = []
        for k, w in want.items():
            same = sum(x == y for x, y in zip(w, got[k]))
            line.append(f"{k} {src.get(k, '')} {same}/{len(w)}".replace("  ", " "))
            errors += same != len(w)
        print(f"[scenario {sc + 1} {rom.year(sc)}] " + ", ".join(line))
        # decode from the WRAM images with the same code
        fake = Rom.__new__(Rom)
        fake.__dict__.update(rom.__dict__)
        fake.loaded_a = fake.block_a = lambda s, w=wa: w
        fake.block_b = lambda s, w=wb: w
        same = [name for name, fn in (("persons", "persons"), ("countries", "countries"), ("houses", "houses"),
                                      ("women", "women"))
                if [{k: v for k, v in r.items() if k != "raw"} for r in getattr(fake, fn)(sc)]
                == [{k: v for k, v in r.items() if k != "raw"} for r in getattr(rom, fn)(sc)]]
        print(f"    decoded from WRAM = decoded from ROM: {', '.join(same)}; "
              f"{len(rom.persons(sc))} persons, {rom.country_count(sc)} countries, {len(rom.houses(sc))} houses, "
              f"{len(rom.women(sc))} women")
        errors += len(same) != 4
    print(f"{'ALL OK' if not errors else f'{errors} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
