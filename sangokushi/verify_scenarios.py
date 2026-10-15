#!/usr/bin/env python3
"""Check the scenario decoding (rom.Rom.scenario_wram, countries, factions, persons) against the game.

For each of the 5 scenarios the game is played from the scenario list to the ruler selection screen (savestate
replay, tools/replay.py). Then
1. the WRAM country (58 x 30), faction (14 x 77) and person (256 x 18) blocks must equal the ROM copies with the
   scenario patches applied, byte for byte;
2. the rulers the screen offers (printf $C1:D337 reading / $C1:D33E name, %s pointers into the name table) must
   be the rulers (+0) of the factions with +1 = 1, in faction order.

Usage: .venv/bin/python sangokushi/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import printf
import replay
import sequences
from rom import (
    COUNTRY_COUNT,
    COUNTRY_SIZE,
    COUNTRY_WRAM,
    DEFAULT_ROM,
    FACTION_COUNT,
    FACTION_SIZE,
    FACTION_WRAM,
    NAME_SIZE,
    NAMES,
    PERSON_COPY,
    SCENARIO_COUNT,
    Rom,
)

BLOCKS = [("country", COUNTRY_WRAM, COUNTRY_COUNT * COUNTRY_SIZE),
          ("faction", FACTION_WRAM, FACTION_COUNT * FACTION_SIZE),
          ("person", PERSON_COPY[1], PERSON_COPY[2])]
READING_FMT, NAME_FMT = 0xC1D337, 0xC1D33E


def name_id(ptr: int, field: int) -> int | None:
    """Name table entry whose byte `field` the CPU address ptr points at (None if it points elsewhere)."""
    p, r = divmod(ptr - 0xC00000 - NAMES - field, NAME_SIZE)
    return p if r == 0 and 0 <= p < 256 else None


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 5 個劇本的 WRAM 初始資料與可選君主")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    save = sequences.end_frame(sequences.TO_SCENARIOS)
    runs = []
    for k in range(1, SCENARIO_COUNT + 1):
        steps = sequences.expand(sequences.scenario(k))
        runs.append({"steps": steps, "shot": sequences.end_frame(steps, 0) + 30,
                     "read": [("wram", a, n) for _, a, n in BLOCKS]})
    results = replay.replay(args.rom, sequences.TO_SCENARIOS, save, runs, extra_lua=printf.LUA)
    errors = 0
    for sc, res in zip(rom.scenarios(), results):
        k, title, year = sc["id"], sc["name"], sc["year"]
        want = rom.scenario_wram(k)
        parts = []
        for (name, a, n), got in zip(BLOCKS, res):
            bad = sum(1 for i in range(n) if got[i] != want[a + i])
            errors += bad
            parts.append(f"{name} {n - bad}/{n}")
        calls = printf.parse(res[-1])
        shown = [name_id(a[0][1], 8) for f, a in calls if f == NAME_FMT]
        reading = [name_id(a[0][1], 0) for f, a in calls if f == READING_FMT]
        rulers = [f["ruler"] for f in rom.factions(k) if f["playable"]]
        names = rom.names()
        ok = shown == rulers and reading == rulers
        errors += not ok
        print(f"scenario {k} {title} ({year}): bytes equal {', '.join(parts)}; rulers "
              + " ".join(names[r]["name"] for r in rulers) + (" OK" if ok else f" NG (screen {shown} {reading})"))
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
