#!/usr/bin/env python3
"""Check the country decoding (names, readings, map positions, country records, rulers) against the game's
country information screen.

Each scenario is played to the player's map and on to 情報 → 国 "どの国の情報を" (savestate, tools/sequences.py).
Each run puts the map cursor on one country's position (rom.Rom.position, written to $0113 / $0115: the game
picks the country by hit-testing that position) and opens the information screen; every code $00:8D60 prints is
logged. The screen must read

  国名 name 君主 ruler-of-the-faction reading 太守 governor 金 産業値 米 収穫高 民 (x 1000) 統治度 城塞値 防災値
  税率 武将数 (persons with WRAM +1 = country | 0x80) 政策 ーー 同盟国 0 兵士数 現 (sum of their 兵数) 控 0

with rom.Rom.country of that scenario (金 and 米 x 1.6: difficulty 1). The computer factions before the player
have already moved by then (開発 spends 金, officers move), so each run first writes the start state
(rom.Rom.scenario_wram: persons, countries, factions; verify_scenarios.py checks it) back to WRAM. Countries
without a faction open no
screen (the game prints nothing for them) and are counted separately.

Usage: .venv/bin/python yokoyama/verify_countries.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences as q
from rom import (
    COUNTRY_COUNT,
    COUNTRY_FIELDS,
    COUNTRY_WRAM,
    COUNTRY_WRAM_SIZE,
    DEFAULT_ROM,
    PERSON_COUNT,
    PERSON_WRAM,
    PERSON_WRAM_SIZE,
    SCENARIO_YEARS,
    Rom,
    decode_fields,
    le16,
)


def expected(rom: Rom, k: int, c: int) -> str:
    w = rom.scenario_wram(k)
    rec = w[COUNTRY_WRAM][COUNTRY_WRAM_SIZE * c + 1:COUNTRY_WRAM_SIZE * c + 17]
    v = decode_fields(rec, COUNTRY_FIELDS)
    persons = [p for p in range(PERSON_COUNT) if w[PERSON_WRAM][PERSON_WRAM_SIZE * p + 1] == c | 0x80]
    troops = sum(le16(w[PERSON_WRAM], PERSON_WRAM_SIZE * p + 4 + 9) for p in persons)
    return (f"国名{rom.country_name(c)}君主{rom.name(rom.rulers(k)[v['勢力']])}{rom.country_reading(c)}"
            f"太守{rom.name(v['太守'])}金{v['金']}産業値{v['産業値']}米{v['米']}収穫高{v['収穫高']}"
            f"民{v['民'] * 1000}統治度{v['統治度']}城塞値{v['城塞値']}防災値{v['防災値']}税率{v['税率']}"
            f"武将数{len(persons)}政策ーー同盟国0兵士数現{troops}控0")


def run(rom: Rom, k: int) -> int:
    boot = q.TO_PICK_INFO[k]
    start = sorted(rom.scenario_wram(k).items())
    runs = [{"wram": start + q.cursor_patch(*rom.position(c)), "steps": q.INFO_STEPS, "shot": q.INFO_SHOT, "read": []}
            for c in range(COUNTRY_COUNT)]
    lua = q.cursor_lua(k) + "CODES_FROM=0\n" + q.CODES_LUA
    results = replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=lua)
    ok = bad = empty = 0
    for c, res in enumerate(results):
        got = rom.text(q.codes(res[-1])).replace("　", "")
        if rom.country(k, c)["勢力"] == 0xFF:
            empty += not got
            bad += bool(got)
            if got:
                print(f"  NG {k} #{c} {rom.country_name(c)}: no faction, but shows {got}")
            continue
        want = expected(rom, k, c)
        if want == got:
            ok += 1
        else:
            bad += 1
            print(f"  NG {k} #{c} {rom.country_name(c)}\n     want {want}\n     got  {got}")
    print(f"scenario {SCENARIO_YEARS[k]}: info screen equal {ok}/{COUNTRY_COUNT - empty}, "
          f"no screen for the {empty} countries without a faction")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證國名、讀音、位置與國資料（情報→国 畫面）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1), help="只跑一個劇本（預設兩個劇本平行跑）")
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k)])
                 for k in (0, 1)]
        errors = sum(p.wait() != 0 for p in procs)
        print(f"{time.time() - t0:.0f} s")
        print("ALL OK" if not errors else "mismatch(es)")
        raise SystemExit(1 if errors else 0)
    raise SystemExit(1 if run(Rom(args.rom), args.scenario) else 0)


if __name__ == "__main__":
    main()
