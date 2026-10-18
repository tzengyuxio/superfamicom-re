#!/usr/bin/env python3
"""Check the name table, readings and person records against the game's officer detail screen.

Each scenario is played (劉備, 中級) to the player's first turn; a savestate is taken there (tools/sequences.py).
Each run writes the start state back (rom.Rom.scenario_wram: the computer factions before the player have already
moved), moves one person into the player's country (WRAM person +0 = faction | 0x80, +1 = country | 0x80; the
officers who are there are moved out with +1 = 0), opens the country panel (the officer lists are built now: only
that person) and 政略 → 人事 → 人材 → 選択 → X (the detail screen), and logs every code $80:8C2E prints.
The screen must read

  name  ruler-of-the-faction  reading  官位  レベル lv  ーー  経験値 exp  体力 hp hp (the / between is not text)  武力 政治力 兵法力 統率力
  疲労度 忠誠度 人望 兵士数  攻撃力 (= 武力 + 士気)  士気 移動力  兵器 ーーーー  武器力 騎 a 弓 b 歩 c

with the values of rom.Rom.person for that scenario (忠誠度 255 = ーー: rulers). The player's ruler shows 君主 for
官位, and the ーー after レベル reads 太守 for the 太守 of the country (rom.Rom.country +1). All 229 persons of all three
scenarios are checked (persons absent from 200 / 215 have an all-zero record and are shown with zeros).

Usage: .venv/bin/python yokoyama2/verify_persons.py [--rom ROM] [--scenario 0|1|2] [--persons 0-228]
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
from rom import DEFAULT_ROM, KANI, PERSON_COUNT, PERSON_WRAM, PERSON_WRAM_SIZE, SCENARIO_YEARS, Rom


def expected(rom: Rom, k: int, p: int, faction: int) -> str:
    v = rom.person(k, p)
    loyalty = str(v["忠誠度"]) if v["忠誠度"] != 255 else "ーー"
    ruler = rom.rulers(k)[faction]
    kani = "君主" if p == ruler else KANI.get(v["官位"], "?")
    governor = "太守" if p == rom.country(k, q.HOME[k])["太守"] else "ーー"
    return (rom.name(p) + rom.name(ruler) + rom.reading(p) + kani
            + f"{v['レベル']}{governor}{v['経験値']}{v['体力']}{v['体力']}{v['武力']}{v['政治力']}{v['兵法力']}"
            + f"{v['統率力']}{v['疲労度']}{loyalty}{v['人望']}{v['兵士数']}{v['武力'] + v['士気']}{v['士気']}"
            + f"{v['移動力']}ーーーー{v['武器'] & 15}{v['武器'] >> 4}{v['武器2']}")


def shown(rom: Rom, raw: bytes) -> str:
    """The detail screen: the codes printed after the X press, without spaces and control codes."""
    return rom.text(c for c in q.codes(raw) if c >= 0x100).replace("　", "")


def detail_runs(rom: Rom, k: int, persons: list[int], read: list) -> list[list[bytes]]:
    """Replay the detail screen of each person (moved into the player's country) in scenario k."""
    home = q.HOME[k]
    faction = rom.country_raw(k, home)[0]
    start = rom.scenario_wram(k)
    there = [i for i in range(PERSON_COUNT) if start[PERSON_WRAM][PERSON_WRAM_SIZE * i + 1] == home | 0x80]
    runs = []
    for p in persons:
        patch = sorted(start.items())
        patch += [(PERSON_WRAM + PERSON_WRAM_SIZE * i + 1, b"\0") for i in there if i != p]
        patch.append((PERSON_WRAM + PERSON_WRAM_SIZE * p, bytes([faction | 0x80, home | 0x80])))
        runs.append({"wram": patch, "steps": q.DETAIL_STEPS, "shot": q.DETAIL_SHOT, "read": read})
    boot = q.TO_MAP[k]
    lua = f"CODES_FROM={q.DETAIL_FROM}\n" + q.CODES_LUA
    return replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=lua)


def run(rom: Rom, k: int, persons: list[int]) -> int:
    faction = rom.country_raw(k, q.HOME[k])[0]
    results = detail_runs(rom, k, persons, [])
    bad = 0
    for p, res in zip(persons, results):
        want, got = expected(rom, k, p, faction), shown(rom, res[-1])
        if want not in got:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} #{p} {rom.name(p)}\n     want {want}\n     got  {got[-160:]}")
    print(f"scenario {SCENARIO_YEARS[k]}: detail screen equal {len(persons) - bad}/{len(persons)}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人名、讀音與人物能力（人事→人材 的武將詳細畫面）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1, 2), help="只跑一個劇本（預設三個劇本平行跑）")
    ap.add_argument("--persons", default=f"0-{PERSON_COUNT - 1}", help="人物編號範圍，如 0-228")
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:  # one Mesen per process: the scenarios run in parallel processes
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k),
                                   "--persons", args.persons]) for k in range(3)]
        errors = sum(p.wait() != 0 for p in procs)
        print(f"{time.time() - t0:.0f} s")
        print("ALL OK" if not errors else "mismatch(es)")
        raise SystemExit(1 if errors else 0)
    lo, _, hi = args.persons.partition("-")
    persons = list(range(int(lo), int(hi or lo) + 1))
    errors = run(Rom(args.rom), args.scenario, persons)
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
