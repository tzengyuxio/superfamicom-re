#!/usr/bin/env python3
"""Check the name table, readings and person records against the game's officer detail screen.

Each scenario is played to the player's map (189: 袁紹, 219: 曹操) and on to 情報 → 武将 "どの国の武将を"; a savestate
is taken there (tools/sequences.py). Each run moves one person into the player's home country (WRAM person +0 =
faction | 0x80, +1 = country | 0x80; the officers who are there are moved out with +1 = 0), opens the country's
officer list and the detail screen of its first (only) officer, and logs every code $00:8D60 prints. The screen
must read

  name  ruler-of-the-faction 軍  reading  レベル lv  経験値 exp  体力 政治力 兵法力 忠誠度 人徳 兵数 統率力
  攻撃力 (= 攻撃力 + 士気) 士気 機動力  武器力 騎 a 弓 b 歩 c

with the values of rom.Rom.person for that scenario (the WRAM record is the ROM record, verify_scenarios.py;
each run first writes that start state back, as the computer factions before the player have already moved).
忠誠度 0 (rulers, persons absent from 219) is shown as ーーー; the titles 君主 / 太守 are left out of the
comparison. All 224 persons of both
scenarios are checked (persons absent from 219 have an all-zero record and are shown with zeros).

Usage: .venv/bin/python yokoyama/verify_persons.py [--rom ROM] [--scenario 0|1] [--persons 0-223]
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
from rom import DEFAULT_ROM, PERSON_COUNT, PERSON_WRAM, PERSON_WRAM_SIZE, SCENARIO_YEARS, Rom


def expected(rom: Rom, k: int, p: int, faction: int) -> str:
    v = rom.person(k, p)
    rulers = rom.rulers(k)
    loyalty = str(v["忠誠度"]) if v["忠誠度"] else "ーーー"
    return (rom.name(p) + rom.name(rulers[faction]) + "軍" + rom.reading(p)
            + f"レベル{v['レベル']}経験値{v['経験値']}体力{v['体力']}攻撃力{v['攻撃力']}政治力{v['政治力']}"
            + f"兵法力{v['兵法力']}忠誠度{loyalty}人徳{v['人徳']}兵数{v['兵数']}統率力{v['統率力']}"
            + f"攻撃力{v['攻撃力'] + v['士気']}士気{v['士気']}機動力{v['機動力']}"
            + f"武器力騎{v['騎']}弓{v['弓']}歩{v['歩']}")


def shown(rom: Rom, raw: bytes) -> str:
    """The detail screen: the codes printed after the last press, without spaces and titles."""
    s = rom.text(q.codes(raw)).replace("　", "").replace("\n", "")
    for t in ("君主", "太守"):
        s = s.replace(t, "")
    return s


def detail_runs(rom: Rom, k: int, persons: list[int], read: list) -> list[list[bytes]]:
    """Replay the detail screen of each person (moved into the home country) in scenario k; the start state
    (rom.Rom.scenario_wram) is written back first, as the computer factions before the player have moved."""
    home, x, y = q.HOME[k]
    faction = rom.country_raw(k, home)[0]
    start = rom.scenario_wram(k)
    there = [i for i in range(PERSON_COUNT) if start[PERSON_WRAM][PERSON_WRAM_SIZE * i + 1] == home | 0x80]
    runs = []
    for p in persons:
        patch = sorted(start.items()) + q.cursor_patch(x, y)
        patch += [(PERSON_WRAM + PERSON_WRAM_SIZE * i + 1, b"\0") for i in there if i != p]
        patch.append((PERSON_WRAM + PERSON_WRAM_SIZE * p, bytes([faction | 0x80, home | 0x80])))
        runs.append({"wram": patch, "steps": q.DETAIL_STEPS, "shot": q.DETAIL_SHOT, "read": read})
    boot = q.TO_PICK_COUNTRY[k]
    lua = q.cursor_lua(k) + f"CODES_FROM={q.DETAIL_FROM}\n" + q.CODES_LUA
    return replay.replay(rom.path, boot, q.end_frame(boot), runs, extra_lua=lua)


def run(rom: Rom, k: int, persons: list[int]) -> int:
    faction = rom.country_raw(k, q.HOME[k][0])[0]
    results = detail_runs(rom, k, persons, [])
    bad = 0
    for p, res in zip(persons, results):
        want, got = expected(rom, k, p, faction), shown(rom, res[-1])
        if want not in got:
            bad += 1
            print(f"  NG {k} #{p} {rom.name(p)}\n     want {want}\n     got  {got[-160:]}")
    print(f"scenario {SCENARIO_YEARS[k]}: detail screen equal {len(persons) - bad}/{len(persons)}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人名、讀音與人物能力（情報→武将 詳細畫面）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1), help="只跑一個劇本（預設兩個劇本平行跑）")
    ap.add_argument("--persons", default=f"0-{PERSON_COUNT - 1}", help="人物編號範圍，如 0-223")
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:  # one Mesen per process: the two scenarios run in two processes
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k),
                                   "--persons", args.persons]) for k in (0, 1)]
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
