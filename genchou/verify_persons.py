#!/usr/bin/env python3
"""Check the person fields of rom.Rom.person (体力, abilities, age) against the game's own card (needs Mesen 2,
about 1 minute).

Scene A of verify_faces.py (scenario 1, 人事 → 政治顧問 → オノン河流域 → カサル) ends on the card that shows the
family record カサル ($7E:4C94): 政治 指揮 / 戦力 魅力 as grades E-A, 体力 current/max and 年齢. For every
person record of the 4 scenarios and of the family block, bytes +18..+21 of that record (体力, 戦闘/政治,
魅力/指揮, age) are overwritten in WRAM before the last press, and the card's BG text (tilemap at VRAM
0xFC80, half-width characters, two rows each: digit d = tile 0x2C + 2d, grade A-E = tile 0x40 + 2k, blank 0) is
read back and must show what the decoding gives: 政治, 指揮, 戦力 (= 戦闘), 魅力, 体力 hp / hp_max, age.

Usage: .venv/bin/python genchou/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import DEFAULT_ROM, GRADES, SCENARIO_COUNT, Rom
from verify_faces import SCENES, SHOT, save_frame

RECORD = 0x4C94                 # family slot 0 (カサル)
TEXT = 0xFC80                   # card text rows, 64 bytes per tilemap row
CELLS = {"政治": (0, 20, 1), "指揮": (0, 27, 1), "戦力": (2, 20, 1), "魅力": (2, 27, 1),
         "体力": (4, 19, 5), "年齢": (6, 20, 2)}   # (row, column, characters)


def char(tile: int) -> str:
    if tile == 0:
        return " "
    if 0x2C <= tile < 0x40 and tile % 2 == 0:
        return str((tile - 0x2C) // 2)
    if 0x40 <= tile < 0x4A and tile % 2 == 0:
        return "ABCDE"[(tile - 0x40) // 2]
    return "/" if tile == 0x0E else "?"


def card(text: bytes) -> dict:
    return {k: "".join(char(text[64 * r + 2 * (c + i)]) for i in range(n)) for k, (r, c, n) in CELLS.items()}


def expect(p: dict) -> dict:
    return {"政治": GRADES[p["政治"]], "指揮": GRADES[p["指揮"]], "戦力": GRADES[p["戦闘"]], "魅力": GRADES[p["魅力"]],
            "体力": f"{p['hp']:2d}/{p['hp_max']:2d}", "年齢": f"{p['age']:2d}"}


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人物欄位（體力、能力、年齡）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    people = [(f"scenario {s + 1}", p) for s in range(SCENARIO_COUNT) for p in rom.persons(s)]
    people += [("family", p) for p in rom.family()]
    sc = SCENES["A"]
    runs = [{"wram": [(RECORD + 18, p["raw"][18:22])], "steps": "a:10", "shot": SHOT,
             "read": [("vram", TEXT, 8 * 64)]} for _, p in people]
    shots = replay(args.rom, sc["boot"], save_frame(sc["boot"]), runs)
    bad, ages = [], []
    for (src, p), (text,) in zip(people, shots):
        got, want = card(text), expect(p)
        if got != want:
            if p["age"] <= 0 and {k: v for k, v in got.items() if k != "年齢"} == \
                    {k: v for k, v in want.items() if k != "年齢"}:
                ages.append(f"{p['name']} {p['age']} -> '{got['年齢']}'")
            else:
                bad.append(f"{src} {p['name']}: card {got} decoded {want}")
    ok = len(people) - len(bad) - len(ages)
    print(f"[card] {ok}/{len(people)} person records: 政治 指揮 戦力 魅力 (grade), 体力 hp/hp_max, 年齢 as decoded")
    if ages:
        print(f"[card] {len(ages)} records with age <= 0 (not born yet) show another age, the rest of the card "
              f"matches: {', '.join(ages[:8])}{' ...' if len(ages) > 8 else ''}")
    for b in bad[:20]:
        print("  NG", b)
    print(f"{'ALL OK' if not bad else f'{len(bad)} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
