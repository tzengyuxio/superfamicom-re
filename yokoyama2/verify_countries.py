#!/usr/bin/env python3
"""Check the country names, readings and country records against the game's country information screen.

Each scenario is played (劉備, 中級) to the player's first turn; a savestate is taken there (tools/sequences.py).
Each run writes the start state back (rom.Rom.scenario_wram: the computer factions and the first month have already
changed some values), puts the map cursor ($0160 / $0162, 1024 x 1024 map pixels) on the country's marker
(MAP_POSITIONS x 16 + 8) and presses X, and logs every code $80:8C2E prints. The screen must read

  国名  君主  reading  太守  政策 ーーーー  金 産業値 米 収穫高 民 (x 1000) 開発度  税率 統治 城塞 防災 砦  武将数 兵士

with the values of rom.Rom.country (武将数 / 兵士 = the persons placed there and the sum of their 兵士数); a country
without a faction shows ーーー for 君主 and 太守 and ーー for 税率 and 統治, and the check stops at 砦. All 35
countries of all three scenarios are checked.

Usage: .venv/bin/python yokoyama2/verify_countries.py [--rom ROM] [--scenario 0|1|2]
"""
import argparse
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences as q
from rom import COUNTRY_COUNT, DEFAULT_ROM, PERSON_COUNT, PERSON_WRAM, PERSON_WRAM_SIZE, SCENARIO_YEARS, Rom

CURSOR = 0x0160               # map cursor x, y (LE16 each, pixels of the 1024 x 1024 map)
PRE = "w30"
STEPS = PRE + " x:10 w300"


def expected(rom: Rom, k: int, c: int) -> str:
    v = rom.country(k, c)
    head = rom.country_name(c)
    if v["勢力"] == 0xFF:
        return (head + "ーーー" + rom.country_reading(c) + "ーーーーーーー" + f"{v['金']}{v['産業値']}{v['米']}"
                + f"{v['収穫高']}{v['民'] * 1000}{v['開発度']}ーーーー{v['城塞値']}{v['防災値']}{v['砦']}")
    start = rom.scenario_wram(k)[PERSON_WRAM]
    here = [p for p in range(PERSON_COUNT) if start[PERSON_WRAM_SIZE * p + 1] == c | 0x80]
    troops = sum(rom.person(k, p)["兵士数"] for p in here)
    return (head + rom.name(rom.rulers(k)[v["勢力"]]) + rom.country_reading(c) + rom.name(v["太守"]) + "ーーーー"
            + f"{v['金']}{v['産業値']}{v['米']}{v['収穫高']}{v['民'] * 1000}{v['開発度']}{v['税率']}{v['統治度']}"
            + f"{v['城塞値']}{v['防災値']}{v['砦']}{len(here)}{troops}")


def run(rom: Rom, k: int) -> int:
    start = sorted(rom.scenario_wram(k).items())
    runs = []
    for c in range(COUNTRY_COUNT):
        x, y = rom.position(c)
        runs.append({"wram": start + [(CURSOR, struct.pack("<HH", 16 * x + 8, 16 * y + 8))], "steps": STEPS,
                     "shot": q.end_frame(STEPS, 0), "read": []})
    boot = q.TO_MAP[k]
    lua = f"CODES_FROM={q.end_frame(PRE, 0)}\n" + q.CODES_LUA
    results = replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=lua)
    bad = 0
    for c, res in enumerate(results):
        want = expected(rom, k, c)
        got = rom.text(x for x in q.codes(res[-1]) if x >= 0x100).replace("　", "")
        if want not in got:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} #{c} {rom.country_name(c)}\n     want {want}\n     got  {got[-120:]}")
    print(f"scenario {SCENARIO_YEARS[k]}: information screen equal {COUNTRY_COUNT - bad}/{COUNTRY_COUNT}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證國名、讀音與國的數值（大地圖 X 的國資訊畫面）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1, 2), help="只跑一個劇本（預設三個劇本平行跑）")
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:  # one Mesen per process: the scenarios run in parallel processes
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k)])
                 for k in range(3)]
        errors = sum(p.wait() != 0 for p in procs)
        print(f"{time.time() - t0:.0f} s")
        print("ALL OK" if not errors else "mismatch(es)")
        raise SystemExit(1 if errors else 0)
    raise SystemExit(1 if run(Rom(args.rom), args.scenario) else 0)


if __name__ == "__main__":
    main()
