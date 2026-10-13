#!/usr/bin/env python3
"""Check the initial game state block and the 6 hero starts against the game (needs Mesen 2, about 1 minute).

大航海時代II has no scenarios; a game starts with one of the 6 heroes (persons 0-5). In Mesen (tools/replay.py):
- At the hero selection screen, WRAM $7E:2000-$8EEE must equal the ROM block rom.INIT byte for byte (the copy
  $7E:F589 makes at power-on; persons, VIPs, women, fleets, ship types, ports and port state all live in it).
- For each hero k (cursor moves on the 2 x 3 selection grid, then no name change and confirm), the game must
  store k at $7E:25FB, the hero's home port HERO_PORTS[k] at $7E:2016, and set the active flag (+7) of fleet
  1 + 10 x country (the hero's start fleet, rom.Rom.fleets). The rest of the hero's person record must be
  unchanged except +35 (re-rolled).

Usage: .venv/bin/python daikoukai2/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import replay
from rom import (
    DEFAULT_ROM,
    FLEET_SIZE,
    FLEETS,
    HERO_PORTS,
    HEROES,
    INIT,
    INIT_SIZE,
    INIT_WRAM,
    PERSON_SIZE,
    PERSONS,
    Rom,
    wram,
)

CURSOR = ["", "right:10 w40", "right:10 w40 right:10 w40", "down:10 w40", "down:10 w40 right:10 w40",
          "down:10 w40 right:10 w40 right:10 w40"]
CHOOSE = " a:10 w200 a:10 w200 right:10 w30 a:10 w200 a:10 w100"
HERO_ID, HERO_PORT = 0x25FB, 0x2016


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證初始狀態區塊與 6 位主角的開始設定")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    persons, fleets = rom.persons(), rom.fleets()
    block = rom.data[INIT:INIT + INIT_SIZE]
    rounds = [([], "w30")] + [([], (CURSOR[k] + CHOOSE).strip()) for k in range(HEROES)]
    mems = list(replay.run(args.rom, replay.BOOT_SELECT, rounds))
    errors = 0
    w = mems[0]["wram"][INIT_WRAM:INIT_WRAM + INIT_SIZE]
    diff = sum(a != b for a, b in zip(w, block))
    print(f"[init] hero selection screen: WRAM $7E:{INIT_WRAM:04X}-{INIT_WRAM + INIT_SIZE - 1:04X} vs ROM "
          f"0x{INIT:05X}: {diff} bytes differ")
    errors += diff != 0
    for k, mem in enumerate(mems[1:]):
        w, p = mem["wram"], persons[k]
        fleet = 1 + 10 * p["country"]
        fa = wram(FLEETS) + FLEET_SIZE * fleet
        pa = wram(PERSONS) + PERSON_SIZE * k
        rec = w[pa:pa + PERSON_SIZE]
        same = all(a == b for i, (a, b) in enumerate(zip(rec, p["raw"])) if i != 35)
        ok = (w[HERO_ID] == k and w[HERO_PORT] == rom.data[HERO_PORTS + k] and w[fa + 7] == 1
              and fleets[fleet]["raw"][7] == 0 and same)
        errors += not ok
        port = rom.ports()[rom.data[HERO_PORTS + k]]["name"]
        print(f"[hero {k}] {p['name']}: $25FB={w[HERO_ID]}, home port $2016={w[HERO_PORT]} ({port}), "
              f"fleet {fleet} active={w[fa + 7]}, record unchanged except +35: {same} -> {'OK' if ok else 'NG'}")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
