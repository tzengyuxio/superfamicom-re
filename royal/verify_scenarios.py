#!/usr/bin/env python3
"""Check the 4 scenario blocks (rom.Rom.scenario) against the game (needs Mesen 2, about 1 minute).

The scenario menu copies the highlighted scenario's block to WRAM (it draws that scenario's houses on the map).
From the menu each scenario is highlighted and started (story -> 1 player) up to the house select screen, and
WRAM $7E:C004 (SCENARIO_SIZE bytes) is compared with the ROM block. The only bytes the game fills in
at the start are the list pointers (character +0, province +0, LE16 WRAM address of a character record): they
are checked as lists instead, i.e. following the pointers from each province must give exactly the characters
whose province (+5) is that province.

Usage: .venv/bin/python royal/verify_scenarios.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import (
    CHAR_COUNT,
    CHAR_SIZE,
    CHAR_START,
    DEFAULT_ROM,
    PROVINCE_COUNT,
    PROVINCE_SIZE,
    PROVINCE_START,
    SCENARIO_COUNT,
    SCENARIO_SIZE,
    SCENARIO_WRAM,
    Rom,
    le16,
)

BOOT = "w1500 start w200 start w200"            # title -> scenario menu


def pointer_bytes() -> set[int]:
    out = set()
    for i in range(CHAR_COUNT):
        out |= {CHAR_START + CHAR_SIZE * i, CHAR_START + CHAR_SIZE * i + 1}
    for p in range(PROVINCE_COUNT):
        out |= {PROVINCE_START + PROVINCE_SIZE * p, PROVINCE_START + PROVINCE_SIZE * p + 1}
    return out


def chains_ok(got: bytes) -> tuple[int, int]:
    """(provinces whose list matches, provinces)."""
    ok = 0
    for p in range(PROVINCE_COUNT):
        want = {i for i in range(CHAR_COUNT) if got[CHAR_START + CHAR_SIZE * i + 5] == p}
        seen, a = [], le16(got, PROVINCE_START + PROVINCE_SIZE * p)
        while a and len(seen) <= CHAR_COUNT:
            i, rest = divmod(a - SCENARIO_WRAM - CHAR_START, CHAR_SIZE)
            if rest or not 0 <= i < CHAR_COUNT:
                break
            seen.append(i)
            a = le16(got, CHAR_START + CHAR_SIZE * i)
        ok += not a and set(seen) == want and len(seen) == len(want)
    return ok, PROVINCE_COUNT


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 4 劇本的 WRAM 映像")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    runs = []
    for s in range(SCENARIO_COUNT):
        steps = "down:10 w30 " * s + "a w200 a w200 a w300"
        runs.append({"steps": steps, "shot": end_frame(steps, 0), "read": [("wram", SCENARIO_WRAM, SCENARIO_SIZE)]})
    got = replay(args.rom, BOOT, end_frame(BOOT), runs)
    skip = pointer_bytes()
    errors = 0
    for s, (w,) in enumerate(got):
        want = rom.scenario(s)
        diff = [i for i in range(SCENARIO_SIZE) if i not in skip and w[i] != want[i]]
        ok, n = chains_ok(w)
        errors += len(diff) + (n - ok)
        print(f"[scenario {s + 1}] WRAM ${SCENARIO_WRAM:04X}: {SCENARIO_SIZE - len(skip) - len(diff)}/"
              f"{SCENARIO_SIZE - len(skip)} bytes equal (+{len(skip)} pointer bytes), province lists {ok}/{n}"
              + (f" NG at {[hex(i) for i in diff[:10]]}" if diff else ""))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
