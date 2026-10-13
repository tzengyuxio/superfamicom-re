#!/usr/bin/env python3
"""Check the scenario images (rom.Rom.image / common) against the game (needs Mesen 2, about 1 minute).

For each of the 3 scenarios the game is started in Mesen (tools/mesen.py, savestate replay haouden/tools/replay.py)
up to the daimyo selection, and WRAM $7E:2000-$7E:872F (filled by the game's loader $C3:0AD1) is compared with
the scenario image (0x6303 bytes) and the common block (0x42D bytes). Bytes the game changes after copying are
listed per table and field (record +offset), so the decoded tables and fields can be told from runtime state.
The person / castle / daimyo tables are also decoded from WRAM and must give the same names and ids as the ROM.

Usage: .venv/bin/python haouden/verify_scenarios.py [--rom ROM]
"""
import argparse
import collections
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import (
    CASTLE_COUNT,
    CASTLE_SIZE,
    CASTLES,
    COMMON_SIZE,
    DAIMYO,
    DAIMYO_COUNT,
    DAIMYO_SIZE,
    DEFAULT_ROM,
    IMAGE_SIZE,
    PERSON_COUNT,
    PERSON_SIZE,
    PERSONS,
    SCENARIO_COUNT,
    WRAM_BASE,
    Rom,
)

# title -> 新しく始める -> settings (cursor on the scenario row); runs: right x sc, a x 5 (rows), a on 実行 -> daimyo selection
BOOT = "w1500 start:10 w200 a:10 w200 a:10 w60"
SAVE_AT = 2060
SHOT = 1100
TABLES = [("daimyo", DAIMYO, DAIMYO_SIZE, DAIMYO_COUNT), ("persons", PERSONS, PERSON_SIZE, PERSON_COUNT),
          ("castles", CASTLES, CASTLE_SIZE, CASTLE_COUNT)]
# Fields the game sets when the scenario starts (bit mask allowed to differ): person +30 low nibble = 気合,
# daimyo +35 / +37 and castle +35 (meaning unsolved), the common block from byte 0x180 on (contents unsolved)
RUNTIME = {"persons+30": 0x0F, "daimyo+35": 0xFF, "daimyo+37": 0xFF, "castles+35": 0xFF, "common": 0xFF}


def where(addr: int) -> str:
    for name, base, size, count in TABLES:
        if base <= addr < base + size * count:
            return f"{name}+{(addr - base) % size}"
    return "header" if addr < DAIMYO else "misc" if addr < 0x8303 else "common"


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（大名、人物、城）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    runs = [{"steps": "right:10 w30 " * sc + "a:10 w60 " * 4 + "a:10 w400 a:10 w300", "shot": SHOT,
             "read": [("wram", WRAM_BASE, IMAGE_SIZE + COMMON_SIZE)]} for sc in range(SCENARIO_COUNT)]
    shots = replay(args.rom, BOOT, SAVE_AT, runs)
    errors = 0
    for sc, (w,) in enumerate(shots):
        want = rom.image(sc) + rom.common()
        diff = collections.Counter(where(WRAM_BASE + i) for i in range(len(want)) if want[i] != w[i])
        unexpected = [i for i in range(len(want))
                      if (want[i] ^ w[i]) & ~RUNTIME.get(where(WRAM_BASE + i), 0)]
        same = sum(a == b for a, b in zip(want, w))
        print(f"[scenario {sc + 1}] WRAM $7E:2000-$7E:872F: {same}/{len(want)} bytes equal the ROM image; "
              f"changed by the game: {dict(sorted(diff.items())) or 'none'}; "
              f"changes outside the known runtime fields: {len(unexpected)}")
        errors += len(unexpected)
        # decode the tables from WRAM with the same code and compare names / ids / stats
        got = Rom.__new__(Rom)
        got.__dict__.update(rom.__dict__)
        got.data = bytearray(rom.data)
        o = rom.off["images"][sc]
        got.data[o:o + IMAGE_SIZE] = w[:IMAGE_SIZE]
        keys = ("slot", "surname", "given", "born", "id", "castle", "政治", "戦闘", "智謀", "采配", "野望")
        a = [tuple(p[k] for k in keys) for p in rom.scenario_persons(sc)]
        b = [tuple(p[k] for k in keys) for p in got.scenario_persons(sc)]
        ck = ("name", "province", "lord", "daimyo", "defense", "kan", "soldiers", "money", "food")
        ca = [tuple(c[k] for k in ck) for c in rom.scenario_castles(sc)]
        cb = [tuple(c[k] for k in ck) for c in got.scenario_castles(sc)]
        da = [(d["slot"], d["head"]) for d in rom.scenario(sc)["daimyo"]]
        db = [(d["slot"], d["head"]) for d in got.scenario(sc)["daimyo"]]
        ok = a == b and ca == cb and da == db
        print(f"  decoded from WRAM: persons {sum(x == y for x, y in zip(a, b))}/{len(a)}, "
              f"castles {sum(x == y for x, y in zip(ca, cb))}/{len(ca)}, daimyo {sum(x == y for x, y in zip(da, db))}"
              f"/{len(da)} identical (names, ids, birth, stats, castle; castle name/国/城主/大名/防/貫/兵/銭/糧)")
        errors += not ok
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
