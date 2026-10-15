#!/usr/bin/env python3
"""Check the country decoding (scenario 1 country records, static country table, states) against the game.

Scenario 1 is played to 曹操's command screen (7国); a savestate is taken there.
1. 領地 list: WRAM country +14 (owner) is set to 1 (曹操's faction) for all 58 countries and 情報 → 領地 is
   opened; its 8 pages x 2 column sets (left / right, L / R) are printed with printf:
     $C4:F99B / $C4:F964  国, 太守 (%s: name table entry +8), 状態 x 2, 金, 兵糧, 鉄
     $C4:F9D4             国, 土地, 洪水, 民忠, 人口, 武将, 在野, 兵数
   金 = +2, 兵糧 = +4, 鉄 = +12, 土地 = +6, 洪水 = 100 - (+7), 民忠 = +10, 人口 = +8, 太守 = +15 (0 shows the
   name of person 0), 武将 = persons there of the owner's faction, 兵数 = their troops / 100, 在野 = 0 (no
   country shows any at the start; which ronin it counts is unsolved).
2. 他国: for every other country the map pointer is moved onto the country's number label (label positions are
   read from OAM in a first, separate Mesen run) and the country is opened. Its detail screen must print
     $C4:F7AC "%2d国 %s" the country number and the state name (%s: STATES + 13 state + 8, state = static
              table byte 0); $C4:F7BC..F7EE 金/土地, 兵糧/洪水, 鉄/城 (+18 low 4 bits), 名馬 (+11)/人口, 武将/民忠,
              在野/兵士.
The game changes a few bytes between the new-game copy and the first command screen (start-of-month
processing; the script lists them), so the expected values are decoded by rom.py from the WRAM of the same run.
The copy itself is checked against the ROM by verify_scenarios.py.

Usage: .venv/bin/python sangokushi/verify_countries.py [--rom ROM]
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import printf
import replay
import sequences
from rom import COUNTRY_COUNT, COUNTRY_SIZE, COUNTRY_WRAM, DEFAULT_ROM, NAME_SIZE, NAMES, STATE_SIZE, STATES, Rom

LIST1, LIST1B, LIST2 = 0xC4F99B, 0xC4F964, 0xC4F9D4
DETAIL = [0xC4F7AC, 0xC4F7BC, 0xC4F7C6, 0xC4F7D0, 0xC4F7DA, 0xC4F7E4, 0xC4F7EE]
POINTER, LABEL_TILE = 0, 0x63            # OAM: sprite 0 is the pointer; the label of country c has tile 0x63 + c
BLOCK = ("wram", 0x2000, 0x1D60)        # country, faction and person records
HOT = (4, 4)                            # put the pointer sprite this far right / down of the label's top left
PAGES = 8


def oam_xy(oam: bytes, k: int) -> tuple[int, int]:
    return oam[4 * k] | (oam[0x200 + k // 4] >> (2 * (k % 4)) & 1) << 8, oam[4 * k + 1]


def labels(rom_path: str) -> dict:
    """Pointer and label positions on the 他国 map (run in its own process: one Mesen per process)."""
    steps = sequences.expand(sequences.INFO_COUNTRY)
    res = replay.replay(rom_path, sequences.TO_MAIN, sequences.end_frame(sequences.TO_MAIN),
                        [{"steps": steps, "shot": sequences.end_frame(steps, 0) + 20, "read": [("oam", 0, 544)]}])
    oam = res[0][0]
    tiles = {oam[4 * k + 2]: oam_xy(oam, k) for k in range(1, 128)}
    # the label of country c is the sprite with tile LABEL_TILE + c; the own country (7) has none on screen: the
    # pointer starts on it
    return {"pointer": oam_xy(oam, POINTER), "labels": [tiles.get(LABEL_TILE + c) for c in range(1, COUNTRY_COUNT + 1)]}


def move(dx: int, dy: int) -> str:
    """Steps that move the map pointer by (dx, dy) pixels (one pixel per frame held)."""
    out = []
    if dx:
        out.append(f"{'right' if dx > 0 else 'left'}:{abs(dx)} w10")
    if dy:
        out.append(f"{'down' if dy > 0 else 'up'}:{abs(dy)} w10")
    return " ".join(out)


def staff(persons: list[dict], c: int, owner: int) -> list[int]:
    """[武将, 在野, 兵士] the game shows for country c owned by faction `owner`: the persons there of that faction
    (person 0 is never counted), 0 (at the start no country shows any 在野; which ronin count is unsolved) and
    their troops / 100."""
    mine = [p for p in persons[1:] if p["country"] == c and owner and p["faction"] == owner]
    return [len(mine), 0, sum(p["troops"] for p in mine) // 100]


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證國資料（領地一覽、他国詳細）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--labels", action="store_true", help="只讀出地圖上各國標籤位置（JSON，內部用）")
    args = ap.parse_args()
    if args.labels:
        print("LABELS " + json.dumps(labels(args.rom)))
        return
    t0 = time.time()
    rom = Rom(args.rom)
    countries = rom.countries(1)
    out = subprocess.run([sys.executable, os.path.abspath(__file__), "--labels", "--rom", args.rom],
                         capture_output=True, text=True, check=True).stdout
    pos = json.loads(next(line for line in out.splitlines() if line.startswith("LABELS "))[7:])
    (px, py), lab = pos["pointer"], pos["labels"]

    # page 1 columns 1 -> R -> columns 2 -> right -> page 2 columns 2 -> R -> columns 1 -> right -> ...
    list_steps = sequences.expand(sequences.INFO_TERRITORY + " r:10 w60 right:10 w60" * (PAGES - 1) + " r:10 w60")
    own = [(COUNTRY_WRAM + COUNTRY_SIZE * c + 14, bytes([1])) for c in range(COUNTRY_COUNT)]
    runs = [{"wram": own, "steps": list_steps, "shot": sequences.end_frame(list_steps, 0) + 20, "read": [BLOCK]}]
    # 他国 cannot open the current country (7, no label on this map); the 領地 list covers it
    others = [c for c in range(1, COUNTRY_COUNT + 1) if lab[c - 1] is not None and lab[c - 1][0] < 256]
    for c in others:
        lx, ly = lab[c - 1]
        steps = sequences.expand(sequences.INFO_COUNTRY + " " + move(lx + HOT[0] - px, ly + HOT[1] - py)
                                 + " w20 a:3 w150 a:10 w300")
        runs.append({"steps": steps, "shot": sequences.end_frame(steps, 0) + 20, "read": [BLOCK]})
    results = replay.replay(args.rom, sequences.TO_MAIN, sequences.end_frame(sequences.TO_MAIN), runs,
                            extra_lua=printf.LUA)

    def name_ptr(p: int) -> int:
        return 0xC00000 + NAMES + NAME_SIZE * p + 8

    def image(res: list[bytes]) -> bytearray:
        w = bytearray(0x20000)
        w[BLOCK[1]:BLOCK[1] + BLOCK[2]] = res[0]
        return w

    # The game changes a few countries between the new-game copy and the first command screen (start-of-month
    # processing), so the screens are compared with the WRAM records of the same run, decoded by rom.py; how far
    # those are from the ROM scenario data is reported (verify_scenarios.py checks the copy itself).
    w0 = image(results[0])
    init = rom.scenario_wram(1)
    changed: dict[int, list[int]] = {}
    for c in range(COUNTRY_COUNT):
        for i in range(COUNTRY_SIZE):
            if i != 14 and w0[COUNTRY_WRAM + COUNTRY_SIZE * c + i] != init[COUNTRY_WRAM + COUNTRY_SIZE * c + i]:
                changed.setdefault(i, []).append(c + 1)
    print("[start] country bytes changed between the scenario copy and the first command screen (owner +14 aside): "
          + "; ".join(f"+{i}: {len(v)} countries" + (f" {v}" if len(v) < 10 else "") for i, v in changed.items()))

    # 1. territory list
    countries, persons = rom.countries(1, w0), rom.persons(1, w0)
    got1, got2 = {}, {}
    for fmt, a in printf.parse(results[0][-1]):
        if fmt in (LIST1, LIST1B):
            got1[a[0]] = [a[1][1], a[4], a[5], a[6]]
        elif fmt == LIST2:
            got2[a[0]] = a[1:]
    bad1 = []
    for k in countries:
        c = k["id"]
        want1 = [name_ptr(k["governor"]), k["gold"], k["food"], k["iron"]]
        want2 = [k["land"], k["flood"], k["loyalty"], k["population"], *staff(persons, c, 1)]
        if got1.get(c) != want1 or got2.get(c) != want2:
            bad1.append((c, got1.get(c), want1, got2.get(c), want2))
    print(f"[領地] {COUNTRY_COUNT - len(bad1)}/{COUNTRY_COUNT} countries: 太守 金 兵糧 鉄 土地 洪水 民忠 人口 武将 在野 兵数 "
          "as decoded")
    for b in bad1[:5]:
        print("  NG", b)

    # 2. 他国 detail
    bad2, shown = [], set()
    for target, res in zip(others, results[1:]):
        calls = {fmt: a for fmt, a in printf.parse(res[-1]) if fmt in DETAIL}
        got = [calls.get(f) for f in DETAIL]
        if got[0] is None or not 1 <= got[0][0] <= COUNTRY_COUNT:
            bad2.append((target, "no detail screen", got))
            continue
        w = image(res)
        persons = rom.persons(1, w)
        k = rom.countries(1, w)[got[0][0] - 1]  # the country the pointer picked (should be the target)
        c = k["id"]
        shown.add(c)
        st = staff(persons, c, k["owner"])
        want = [[c, ("s", 0xC00000 + STATES + STATE_SIZE * k["state"] + 8)], [k["gold"], k["land"]],
                [k["food"], k["flood"]], [k["iron"], k["castle"]], [k["horses"], k["population"]],
                [st[0], k["loyalty"]], [st[1], st[2]]]
        if got != want:
            bad2.append((c, got, want))
    missed = sorted(set(others) - shown)
    print(f"[他国] {len(shown) - len(bad2)}/{len(shown)} countries opened show number, state ("
          + "、".join(s["name"] for s in rom.states()) + "), 金 土地 兵糧 洪水 鉄 城 名馬 人口 武将 民忠 在野 兵士 "
          f"as decoded; not reached by the pointer: {missed or 'none'} (7 = own country, not offered)")
    for b in bad2[:5]:
        print("  NG", b)
    bad2 += missed
    print(f"{time.time() - t0:.0f} s")
    errors = len(bad1) + len(bad2)
    print("ALL OK" if not errors else f"{errors} mismatch(es)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
