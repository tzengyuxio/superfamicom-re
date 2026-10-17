#!/usr/bin/env python3
"""Check the scenario tables against the game in Mesen.

PRESENT MODE: savestate on the scenario menu; each run moves the cursor to one of the 6 scenarios and presses A
through the setup pages (scenario page, YES, company page, name page, level, confirm). Checked:
1. the scenario page draws the name ($01:D5E9) and the description (PEA at $06:9973) — text routine $01:9392;
2. WRAM $280C = scenario, $2812 / $2810 = start / end year (immediates of the switch at $06:A4E3; the game
   start at $07:92AF decrements $2812 once, so it reads start - 1 after the last page);
3. WRAM $4417 (47 x LE16) = the population record rom.population(start year) ($07:A403);
4. the confirm page draws the scenario name and the level BEGINNER ($01:D6C1).
FREE MODE: savestate on the PRESENT / FREE menu; the 3 lengths are chosen with the start year left at its
default, plus short scenarios started 1-4 years later (R on the year page, one year per press); checked: the page draws the
length name and description, $280C = 6-8, $2810 = start + 4 / + 9 (long: 1978-1997), $4417 = the record of the
start year (so the year limits 1980 / 1985 / 1990 / 1995 are crossed).

Usage: .venv/bin/python topman2/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import tm2
from replay import end_frame, replay
from rom import (
    DEFAULT_ROM,
    PREF_COUNT,
    SCENARIO_COUNT,
    WRAM_END_YEAR,
    WRAM_POP,
    WRAM_SCENARIO,
    WRAM_START_YEAR,
    Rom,
)

READS = [("wram", WRAM_SCENARIO, 2), ("wram", WRAM_END_YEAR, 2), ("wram", WRAM_START_YEAR, 2),
         ("wram", WRAM_POP, 2 * PREF_COUNT)]
SETUP = " a:10 w300" * 9      # scenario, YES, company page, name page, level, confirm, ... game start
FREE_SETUP = " a:10 w300" * 16  # + year page, home / office change and company name change pages


def check(rom: Rom, r: list[bytes], scenario: int, start: int, end: int, name: str, desc: str) -> bool:
    shown = tm2.texts(tm2.parse(r[-1]))
    # $06:A4E3 / $06:A400 store the start year; the game start ($07:92AF) decrements it once
    got = (int.from_bytes(r[0], "little"), int.from_bytes(r[2], "little") + 1, int.from_bytes(r[1], "little"))
    pop = [int.from_bytes(r[3][2 * i:2 * i + 2], "little") for i in range(PREF_COUNT)]
    checks = {"name": name in shown, "description": desc in shown, "scenario/years": got == (scenario, start, end),
              "population": pop == rom.population(start)}
    ok = all(checks.values())
    print(f"  {name} {start}-{end}: " + ", ".join(f"{k} {'OK' if v else 'NG'}" for k, v in checks.items())
          + ("" if ok else f" (WRAM {got})"))
    return ok


def present(rom: Rom) -> int:
    sc = rom.scenarios()
    runs = [{"steps": "w20" + " down:3 w40" * s + SETUP, "shot": end_frame("w20" + " down:3 w40" * s + SETUP, 0) + 60,
             "read": READS} for s in range(SCENARIO_COUNT)]
    res = replay(rom.path, tm2.TO_SCENARIO_MENU, end_frame(tm2.TO_SCENARIO_MENU), runs,
                 extra_lua=tm2.COLLECT_LUA + tm2.TEXT_LUA)
    ok = 0
    for s, r in enumerate(res):
        shown = tm2.texts(tm2.parse(r[-1]))
        level_ok = rom.levels()[0] in shown
        good = check(rom, r, s, sc[s]["start_year"], sc[s]["end_year"], sc[s]["name"], sc[s]["description"])
        ok += good and level_ok
    print(f"[PRESENT] scenarios {ok}/{SCENARIO_COUNT}")
    return SCENARIO_COUNT - ok


def free(rom: Rom) -> int:
    """(length, years later than the default on the year page)"""
    sc = rom.scenarios()
    to_mode = tm2.TITLE + " a:10 w200"
    cases = [(6, 0), (7, 0), (8, 0), (6, 1), (6, 2), (6, 3), (6, 4)]
    runs = []
    for length, later in cases:
        steps = ("w20 down:3 w60 a:10 w300" + " down:3 w40" * (length - 6) + " a:10 w300"
                 + " r:4 w30" * later + FREE_SETUP)
        runs.append({"steps": steps, "shot": end_frame(steps, 0) + 60, "read": READS})
    res = replay(rom.path, to_mode, end_frame(to_mode), runs, extra_lua=tm2.COLLECT_LUA + tm2.TEXT_LUA)
    ok = 0
    default = None
    for (length, later), r in zip(cases, res):
        start = int.from_bytes(r[2], "little") + 1
        if later == 0 and length == 6:
            default = start
        s = sc[length]
        want_start = s["start_year"] or (default + later if default else start)
        want_end = s["end_year"] or want_start + (4 if length == 6 else 9)
        ok += check(rom, r, length, want_start, want_end, s["name"], s["description"])
    print(f"[FREE] runs {ok}/{len(cases)} (default start year {default})")
    return len(cases) - ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--part", choices=["present", "free"], help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.part:   # one Mesen per process
        bad = (present if args.part == "present" else free)(Rom(args.rom))
        print(f"PART_BAD {bad}", flush=True)
        return
    t = time.time()
    bad = 0
    for part in ("present", "free"):
        out = subprocess.run([sys.executable, __file__, "--rom", args.rom, "--part", part], check=False,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
        for line in out.splitlines():
            if line.startswith("PART_BAD"):
                bad += int(line.split()[1])
            else:
                print(line)
        bad += "PART_BAD" not in out
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
