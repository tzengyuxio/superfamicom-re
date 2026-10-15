#!/usr/bin/env python3
"""Check the person decoding (name table, person records) against the game's 武将 list.

Scenario 1 is played to 曹操's command screen (7国); a savestate is taken there. Each run moves six persons into
7国 / 曹操's faction (WRAM person +10 = 7, +11 = 1; the six generals who are there are moved out with +11 = 0),
opens 情報 → 武将 and switches to the second column set (R). The list is printed with printf:
  $C1:D341 "%s"                         name: pointer into the name table (entry p +8)
  $C1:D417 "%4s%3d%3d%3d%3d%3d%3d"      身分, 年齢, 身体, 知力, 武力, カリスマ, 運勢
  $C1:D461 "%3d"                        忠誠 (not for the ruler)
  $C1:D469 "%3d%3d%3d%3d%s"             兵士 / 100, 兵忠, 訓練, 武装, 水軍 (扱 / 不)
Every person 1-255 must show its name, age = scenario year - birth year, the five stats, loyalty, troops and the
水軍 flag (person +7 bit 0) as rom.Rom.persons decodes them. 兵忠 (+12), 武装 (+13) and 訓練 (+14) are 0 for
everybody at the start, so the moved persons get test values there (troop_test) that the list must show.
Person 0 (a second 曹操 entry: face 3, lower stats) is not listed by the game and is skipped.

Informative extra: the five stats against kaodata-re's person table (--ext; another release of the game).

Usage: .venv/bin/python sangokushi/verify_persons.py [--rom ROM] [--ext CSV]
"""
import argparse
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import printf
import replay
import sequences
from rom import DEFAULT_ROM, NAME_SIZE, NAMES, PERSON_COUNT, PERSON_SIZE, PERSON_WRAM, Rom

COUNTRY, FACTION = 7, 1                  # 曹操's country and faction number in scenario 1
NAME, ROW1, LOYALTY, ROW2 = 0xC1D341, 0xC1D417, 0xC1D461, 0xC1D469
NAVY = {0xC1D488: 1, 0xC1D48B: 0}       # "扱" / "不"
RANKS = {0xC1D3D4: "君主", 0xC1D3DE: "現役"}
BATCH = 6
EXT = os.path.expanduser("~/works/kaodata-re/PERSONS_TABLE/san1_persons_s1.csv")
EXT_STATS = ["身體", "知力", "武力", "信服力", "運勢"]


def troop_test(p: int) -> list[int]:
    """Test values written to person +12 (兵忠), +13 (武装), +14 (訓練): all are 0 at the start."""
    return [p % 97 + 1, p % 89 + 2, p % 83 + 3]


def name_id(ptr: int) -> int | None:
    p, r = divmod(ptr - 0xC00000 - NAMES - 8, NAME_SIZE)
    return p if r == 0 and 0 <= p < PERSON_COUNT else None


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人名表與人物能力（情報→武将 一覽）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--ext", default=EXT, help="外部人物表（只做參考比對）")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    persons = rom.persons(1)
    year = rom.scenarios()[0]["year"]
    here = [p["id"] for p in persons if p["country"] == COUNTRY and p["faction"] == FACTION and p["id"] > 1]
    targets = list(range(2, PERSON_COUNT))
    batches = [targets[i:i + BATCH] for i in range(0, len(targets), BATCH)]
    steps = sequences.expand(sequences.INFO_PERSONS + " r:10 w150")
    runs = []
    for b in batches:
        wram = [(PERSON_WRAM + PERSON_SIZE * p + 11, bytes([0])) for p in here]
        wram += [(PERSON_WRAM + PERSON_SIZE * p + 10, bytes([COUNTRY, FACTION, *troop_test(p)])) for p in b]
        runs.append({"wram": wram, "steps": steps, "shot": sequences.end_frame(steps, 0) + 20, "read": []})
    save = sequences.end_frame(sequences.TO_MAIN)
    results = replay.replay(args.rom, sequences.TO_MAIN, save, runs, extra_lua=printf.LUA)


    seen: dict[int, dict] = {}
    unexpected = []
    for b, res in zip(batches, results):
        cur = None
        for fmt, a in printf.parse(res[-1]):
            if fmt == NAME:
                cur = name_id(a[0][1])
                if cur is None or cur not in b + [1]:
                    unexpected.append((b, a))
                    cur = None
                else:
                    seen.setdefault(cur, {})
            elif cur is None:
                continue
            elif fmt == ROW1:
                seen[cur]["row1"] = [RANKS.get(a[0][1], hex(a[0][1]))] + a[1:]
            elif fmt == LOYALTY:
                seen[cur]["loyalty"] = a[0]
            elif fmt == ROW2:
                seen[cur]["row2"] = a[:4] + [NAVY.get(a[4][1], hex(a[4][1]))]

    rulers = {f["ruler"] for f in rom.factions(1)}
    bad = []
    for p in [1] + targets:
        q = dict(persons[p])
        if p > 1:
            q["morale"], q["arms"], q["training"] = troop_test(p)
        want = {"row1": ["君主" if p in rulers else "現役", (year - q["born"]) & 0xFFFF, *q["stats"]],
                "row2": [q["troops"] // 100, q["morale"], q["training"], q["arms"], q["navy"]]}
        if p not in rulers:  # a faction's ruler (faction +0) is shown as 君主, with "---" for loyalty
            want["loyalty"] = q["loyalty"]
        got = seen.get(p, {})
        if got != want:
            bad.append((p, q["name"], got, want))
    print(f"[list] {len(targets) + 1 - len(bad)}/{len(targets) + 1} persons (1-255) shown as decoded "
          f"(name, 身分, age, 身体 知力 武力 カリスマ 運勢, 忠誠, 兵士/100, 兵忠, 訓練, 武装, 水軍); {len(batches)} runs")
    for p, name, got, want in bad[:10]:
        print(f"  NG {p} {name}: game {got} / ROM {want}")
    if unexpected:
        print(f"  unexpected names: {unexpected[:5]}")
    external(persons, args.ext)
    print(f"{time.time() - t0:.0f} s")
    errors = len(bad) + len(unexpected)
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


def external(persons: list[dict], path: str) -> None:
    """Informative: the five stats against kaodata-re's 三國志 person table (ID = person - 1; another release of
    the game, so differences are listed, not counted as errors)."""
    if not os.path.exists(path):
        print(f"[EXT] {path} not found, skipped")
        return
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    diff = []
    for r in rows:
        p = persons[int(r["ID"]) + 1]
        ext = [int(r[k]) for k in EXT_STATS]
        if ext != p["stats"]:
            diff.append(f"{p['id']} {p['name']} {ext}→{p['stats']}")
    print(f"[EXT] {len(rows) - len(diff)}/{len(rows)} persons with the same 身体 知力 武力 カリスマ 運勢 as "
          f"{os.path.basename(path)}; differ (theirs→ROM): {'; '.join(diff) or '-'}")


if __name__ == "__main__":
    main()
