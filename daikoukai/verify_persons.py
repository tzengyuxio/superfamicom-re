#!/usr/bin/env python3
"""Check the new-game state (rom.INIT: persons, abilities, fleets, building flags) and the file handles the
decoders rely on, against the game (Mesen 2, ~30 s).

1. Right after the game copies its initial block to WRAM (frame ~2044, the copy runs from RAM at $00:006F),
   WRAM $7E:DF02.. must equal ROM INIT.. (INIT_SIZE bytes).
2. In Lisbon after the prologue (frame 11766), with the game running on that state:
   - the person table ($E444, 41 x 7) equals the ROM (the game keeps it);
   - the ability rows of the 20 mates ($EAC0 + 10k) equal the ROM (the player's row is rolled at the start);
   - the player's name pointer reaches WRAM $EAB0, which holds レオン (the default name) as rom.text reads it;
   - fleet record 0 ($E564) is at Lisbon's location from the port table; the building flags ($EE78) equal the ROM;
   - the file handles hold the ROM offsets used by rom.py: $7E:1E1C = DATA (names, ports, palettes, map
     tables) and $7E:1E0E = TOWN_FILE (graphics maps).

Usage: .venv/bin/python daikoukai/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from boot import NEW_GAME
from replay import presses, replay
from rom import (
    DATA,
    DEFAULT_ROM,
    FLEET_START,
    INIT,
    INIT_SIZE,
    INIT_WRAM,
    PERSON_COUNT,
    PERSON_SIZE,
    PERSON_START,
    PORT_SIZE,
    PORTS,
    STAT_COUNT,
    STAT_SIZE,
    STAT_START,
    TOWN_FILE,
    TOWN_FLAGS,
    Rom,
    le16,
    text,
)

SAVE = 2126
TOWN = 11766


def relative_steps(steps: str, start: int) -> str:
    """The presses of `steps` (from power-on) that come after frame `start`, as a script starting there."""
    out, f = [], start
    for fr, b, hold in presses(steps, 10):
        if fr < start:
            continue
        out += [f"w{fr - f}", f"{b}:{hold}"]
        f = fr + hold + 20
    return " ".join(out)


def handle_offset(h: bytes) -> int:
    return (le16(h, 0) & 0x7F) * 0x8000 + (le16(h, 2) & 0x7FFF)


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證開局狀態（人物、能力、艦隊、建物旗標）與檔案 handle")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    w = INIT_WRAM
    runs = [{"steps": "", "shot": 5, "read": [("wram", INIT_WRAM, INIT_SIZE)]},
            {"steps": relative_steps(NEW_GAME, SAVE), "shot": TOWN - SAVE,
             "read": [("wram", w + PERSON_START, PERSON_COUNT * PERSON_SIZE),
                      ("wram", w + STAT_START, STAT_COUNT * STAT_SIZE), ("wram", 0xEAB0, 16),
                      ("wram", w + FLEET_START, 4), ("wram", w + TOWN_FLAGS, 70),
                      ("wram", 0x1E1C, 4), ("wram", 0x1E0E, 4)]}]
    (block,), (persons, stats, name, fleet, flags, h_data, h_town) = replay(args.rom, NEW_GAME, SAVE, runs)
    init = rom.data[INIT:INIT + INIT_SIZE]
    checks = [
        (f"WRAM $7E:{INIT_WRAM:04X} = ROM 0x{INIT:X} ({INIT_SIZE} B) after the copy",
         sum(a == b for a, b in zip(block, init)) == INIT_SIZE),
        ("person table (41 x 7) unchanged in Lisbon", persons == init[PERSON_START:][:len(persons)]),
        ("mates' ability rows 1-20", stats[STAT_SIZE:] == init[STAT_START + STAT_SIZE:][:len(stats) - STAT_SIZE]),
        (f"player name at $EAB0 = {text(name)!r} = rom.persons()[0]", text(name) == rom.persons()[0]["name"]),
        ("fleet 0 at Lisbon's port location", fleet == rom.data[PORTS + 15:PORTS + 15 + 4]),
        ("building flags $EE78 (70 ports)", flags == init[TOWN_FLAGS:TOWN_FLAGS + 70]),
        (f"handle $1E1C -> file 0x{handle_offset(h_data):X} (DATA 0x{DATA:X})", handle_offset(h_data) == DATA),
        (f"handle $1E0E -> file 0x{handle_offset(h_town):X} (TOWN_FILE 0x{TOWN_FILE:X})",
         handle_offset(h_town) == TOWN_FILE),
    ]
    for label, ok in checks:
        print(f"[{'OK' if ok else 'NG'}] {label}")
    diff = [k for k in range(len(block)) if block[k] != init[k]]
    if diff:
        print("  differing WRAM:", " ".join(f"${INIT_WRAM + k:04X}" for k in diff[:16]))
    print(f"(player's rolled abilities: {list(stats[:6])}, ROM default {list(init[STAT_START:STAT_START + 6])}; "
          f"port record of Lisbon = DATA + 0x{PORTS - DATA:X}, {PORT_SIZE} B)")
    errors = sum(not ok for _, ok in checks)
    print(f"{time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
