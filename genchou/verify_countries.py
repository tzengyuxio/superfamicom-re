#!/usr/bin/env python3
"""Check country fields of rom.Rom.countries (金 食糧 人口 and the three values +20..+22) against the main
screen's country panel (needs Mesen 2, about 1 minute).

Scenario 1 is started (savestate replay, tools/replay.py; the save is taken at "戦闘を見ますか", before
the main screen is drawn). For every country record of the 4 scenarios, bytes +9..+14 and +20..+22 of country 0 (オノン河流域,
WRAM $7E:430A) are overwritten there; after the setup questions and the opening event the panel at the bottom
shows the player's country: 金, 食糧 and 人口 on the left (BG3 rows 20 / 22 / 24, columns 7-10) and three numbers
with icons on the right (columns 19-22). The panel (half-width digits, tile 0x2C + 2d, two rows each) must show
gold, food, population, +20, +21 and +22 in decimal. (The red numbers next to 金 and 食糧 are computed by the
game and not checked.)

Usage: .venv/bin/python genchou/verify_countries.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import A_WRAM, COUNTRIES_AT, DEFAULT_ROM, SCENARIO_COUNT, Rom
from verify_faces import save_frame

# title, new game, scenario 1, one player, モンゴル族, yes, 他国の戦争 yes, up to "戦闘を見ますか"; then the
# defaults up to "ご自分で命令を実行なさいますか" with the panel
BOOT = "w2100 start:30 w100 start:4 w300" + " a:10 w200" * 8
STEPS = "a:10 w300 " * 3
SHOT = 3 * 330
COUNTRY0 = A_WRAM + COUNTRIES_AT
TEXT = 0xF800 + 20 * 64                    # BG3 tilemap rows 20-25
FIELDS = {"金": (0, 7, 4), "食糧": (2, 7, 4), "人口": (4, 7, 4),
          "+20": (0, 19, 4), "+21": (2, 19, 4), "+22": (4, 19, 4)}   # (row, column, characters)


def number(text: bytes, row: int, col: int, n: int) -> str:
    out = ""
    for i in range(n):
        t = text[64 * row + 2 * (col + i)]
        out += str((t - 0x2C) // 2) if 0x2C <= t < 0x40 and t % 2 == 0 else " " if t in (0, 0xC4) else "?"
    return out.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證國的欄位（金、食糧、人口、+20..+22）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    records = [(sc, c) for sc in range(SCENARIO_COUNT) for c in rom.countries(sc)]
    runs = [{"wram": [(COUNTRY0 + 9, c["raw"][9:15]), (COUNTRY0 + 20, c["raw"][20:23])], "steps": STEPS,
             "shot": SHOT, "read": [("vram", TEXT, 6 * 64)]} for _, c in records]
    shots = replay(args.rom, BOOT, save_frame(BOOT), runs)
    bad = []
    for (sc, c), (text,) in zip(records, shots):
        got = {k: number(text, *v) for k, v in FIELDS.items()}
        want = {"金": str(c["gold"]), "食糧": str(c["food"]), "人口": str(c["population"]),
                "+20": str(c["raw"][20]), "+21": str(c["raw"][21]), "+22": str(c["raw"][22])}
        if got != want:
            bad.append(f"scenario {sc + 1} country {c['id']}: panel {got} decoded {want}")
    print(f"[panel] {len(records) - len(bad)}/{len(records)} country records: 金 食糧 人口 and +20 +21 +22 shown as "
          f"decoded")
    for b in bad[:20]:
        print("  NG", b)
    print(f"{'ALL OK' if not bad else f'{len(bad)} problem(s)'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
