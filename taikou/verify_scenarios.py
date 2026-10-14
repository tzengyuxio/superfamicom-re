#!/usr/bin/env python3
"""Check the start-of-game block (rom.Rom.init_block and the tables in it) against the game (needs Mesen 2,
about 1 minute).

A new game is started in Mesen up to the type selection screen (tools/sequences.TO_TYPES). By then the game has
copied ROM 0x183F0-0x1C31C to $7E:2000-$7E:5F2C; the whole range is read back and compared byte by byte. The
first 0x3A bytes (header: date, map position and flags) are already being changed by the game and are only
reported. Then the faction (20 x 33 at $7E:2213), person (241 x 54 at $7E:24A7) and castle state (123 x 16 at
$7E:577D) tables are compared record by record.

Usage: .venv/bin/python taikou/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import (
    CASTLE_STATE_COUNT,
    CASTLE_STATE_SIZE,
    CASTLE_STATES,
    DEFAULT_ROM,
    FACTION_COUNT,
    FACTION_SIZE,
    FACTIONS,
    INIT_SIZE,
    PERSON_COUNT,
    PERSON_SIZE,
    PERSONS,
    WRAM_BASE,
    Rom,
)
from sequences import TO_TYPES, end_frame, expand

HEADER = 0x3A
SAVE_AT = end_frame(TO_TYPES) - 60


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證開局初始區塊")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    (wram,), = replay(args.rom, expand(TO_TYPES), SAVE_AT, [{"shot": 100, "read": [("wram", WRAM_BASE, INIT_SIZE)]}])
    init = rom.init_block()
    diff = [i for i in range(INIT_SIZE) if wram[i] != init[i]]
    body = [i for i in diff if i >= HEADER]
    print(f"[block] $7E:{WRAM_BASE + HEADER:04X}-$7E:{WRAM_BASE + INIT_SIZE - 1:04X} vs ROM 0x{0x183F0 + HEADER:X}: "
          f"{INIT_SIZE - HEADER - len(body)}/{INIT_SIZE - HEADER} bytes equal"
          + (f" (first differences at {[hex(WRAM_BASE + i) for i in body[:10]]})" if body else ""))
    print(f"  header $7E:2000-$7E:{WRAM_BASE + HEADER - 1:04X}: {HEADER - len(diff) + len(body)}/{HEADER} bytes "
          "equal (changed by the game before this screen, not counted)")
    errors = len(body)
    for label, addr, count, size in (("factions", FACTIONS, FACTION_COUNT, FACTION_SIZE),
                                     ("persons", PERSONS, PERSON_COUNT, PERSON_SIZE),
                                     ("castle states", CASTLE_STATES, CASTLE_STATE_COUNT, CASTLE_STATE_SIZE)):
        o = addr - WRAM_BASE
        recs = rom.wram_table(addr, count, size)
        ok = sum(wram[o + size * k:o + size * (k + 1)] == recs[k] for k in range(count))
        print(f"[{label}] {ok}/{count} records of {size} bytes at $7E:{addr:04X} equal")
        errors += count - ok
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
