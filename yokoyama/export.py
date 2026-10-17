#!/usr/bin/env python3
"""匯出 SFC 横山光輝 三国志 的人物、劇本、國、勢力、地形、頭像與大地圖。

Usage: .venv/bin/python yokoyama/export.py [--rom ROM] [--out DIR]

Writes persons.csv (224), scenario_persons.csv (2 x 224: placement and all fields), countries.csv (31),
scenario_countries.csv (2 x 31), factions.csv (2 x 15), terrain.csv (8 kinds) (+ yokoyama.xlsx when openpyxl is
installed), faces/ (224 PNG) and faces.png (all of them on one sheet), map.png (1024 x 1024, no markers),
map_189.png / map_219.png (with the start-of-scenario city markers) and terrain.png (64 x 64 cells over the map).
"""
import argparse
import csv
import os
import sys

from PIL import Image
from rom import (
    COUNTRY_COUNT,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    FACTION_COUNT,
    MAP_BANK,
    PERSON_COUNT,
    PLACE_KINDS,
    SCENARIO_YEARS,
    TERRAIN_KINDS,
    TERRAIN_SIZE,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PERSON_COLUMNS = ["体力", "攻撃力", "兵法力", "政治力", "忠誠度", "人徳", "経験値", "レベル", "統率力", "兵数", "士気",
                  "機動力", "騎", "弓", "歩"]
TERRAIN_COLOURS = [(200, 40, 40), (0, 0, 0), (120, 90, 60), (170, 140, 90), (40, 120, 40), (190, 220, 130),
                   (230, 200, 60), (60, 110, 220)]


def place_text(rom: Rom, k: int, p: int) -> dict:
    kind, country, ref, year, _ = rom.place(k, p)
    who = rom.name(ref) if kind in (2, 4, 5) and ref < PERSON_COUNT else ""
    faction = rom.name(rom.rulers(k)[ref]) + "軍" if kind == 3 and ref < FACTION_COUNT else ""
    return {"配置": PLACE_KINDS.get(kind, f"{kind:02X}"),
            "國": rom.country_name(country) if kind in (0, 1, 3) and country < COUNTRY_COUNT else "",
            "關係人物": who or faction, "登場年": year if kind in (1, 2, 3, 4, 5) else "",
            "配置(原始)": rom.place(k, p).hex(" ").upper()}


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in range(PERSON_COUNT):
        row = {"Id": p, "名前": rom.name(p), "読み": rom.reading(p),
               "頭像部品": rom.face_parts(p).hex(" ").upper()}
        for k, year in enumerate(SCENARIO_YEARS):
            pl = place_text(rom, k, p)
            row[f"{year}配置"] = pl["配置"] + (f"（{pl['國']}）" if pl["國"] else "")
        rows.append(row)
    return rows


def scenario_person_rows(rom: Rom) -> list[dict]:
    rows = []
    for k, year in enumerate(SCENARIO_YEARS):
        start = rom.scenario_wram(k)[0x0800]
        for p in range(PERSON_COUNT):
            v = rom.person(k, p)
            head = start[22 * p:22 * p + 2]
            row = {"劇本": year, "Id": p, "名前": rom.name(p), **place_text(rom, k, p),
                   "勢力": rom.name(rom.rulers(k)[head[0] & 0x0F]) + "軍" if head[0] & 0xC0 == 0x80 else ""}
            row.update({c: v[c] for c in PERSON_COLUMNS})
            row["攻撃力(部隊)"] = v["攻撃力"] + v["士気"]
            row["武器(原始)"] = f"{v['武器_raw']:02X}"
            row["原始"] = rom.person_raw(k, p).hex(" ").upper()
            rows.append(row)
    return rows


def country_rows(rom: Rom) -> list[dict]:
    rows = []
    for c in range(COUNTRY_COUNT):
        x, y = rom.position(c)
        rows.append({"Id": c, "國名": rom.country_name(c), "読み": rom.country_reading(c), "位置X": x, "位置Y": y})
    return rows


def scenario_country_rows(rom: Rom) -> list[dict]:
    rows = []
    for k, year in enumerate(SCENARIO_YEARS):
        for c in range(COUNTRY_COUNT):
            v = rom.country(k, c)
            f = v.pop("勢力")
            row = {"劇本": year, "Id": c, "國名": rom.country_name(c),
                   "勢力": rom.name(rom.rulers(k)[f]) + "軍" if f != 0xFF else "",
                   "太守": rom.name(v.pop("太守")) if f != 0xFF else ""}
            v["民"] *= 1000
            row.update(v)
            row["原始"] = rom.country_raw(k, c).hex(" ").upper()
            rows.append(row)
    return rows


def faction_rows(rom: Rom) -> list[dict]:
    rows = []
    for k, year in enumerate(SCENARIO_YEARS):
        rulers = rom.rulers(k)
        for f in range(FACTION_COUNT):
            r = rulers[f]
            if r == 0xFF:
                continue
            countries = [rom.country_name(c) for c in range(COUNTRY_COUNT) if rom.country(k, c)["勢力"] == f]
            rows.append({"劇本": year, "勢力": f, "君主": rom.name(r), "國數": len(countries),
                         "國": "、".join(countries)})
    return rows


def terrain_rows(rom: Rom) -> list[dict]:
    cells = [rom.terrain(x, y) for y in range(TERRAIN_SIZE) for x in range(TERRAIN_SIZE)]
    blank = {0: "（城）", 1: "（不可通行）"}   # no name in the table
    return [{"Id": t, "地形": rom.terrain_name(t) or blank[t], "移動等級": rom.terrain_move(t),
             "格數": cells.count(t)} for t in range(TERRAIN_KINDS)]


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"已匯出 {len(rows)} 筆 → {path}")


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(list(rows[0]))
        for r in rows:
            ws.append(list(r.values()))
        ws.freeze_panes = "B2"
    wb.save(path)
    print(f"已匯出 → {path}")


def map_image(rom: Rom, vram: bytes) -> Image.Image:
    pal = rom.map_screen_palette(0)
    im = Image.new("P", (1024, 1024))
    im.putdata(rom.map_image_pixels(vram))
    im.putpalette([v for c in pal for v in c])
    return im.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 横山光輝 三国志 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "劇本人物": scenario_person_rows(rom), "國": country_rows(rom),
              "劇本國": scenario_country_rows(rom), "勢力": faction_rows(rom), "地形": terrain_rows(rom)}
    names = ("persons", "scenario_persons", "countries", "scenario_countries", "factions", "terrain")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "yokoyama.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    cols, cw, ch = 16, FACE_W + 4, FACE_H + 4
    sheet = Image.new("RGB", (cols * cw, (PERSON_COUNT + cols - 1) // cols * ch), (40, 40, 40))
    for p in range(PERSON_COUNT):
        im = Image.new("RGBA", (FACE_W, FACE_H))
        im.putdata([(*c, 255) if c else (0, 0, 0, 0) for c in rom.face_rgb(p)])
        im.save(os.path.join(faces, f"{p:03d}_{rom.name(p)}.png"))
        sheet.paste(im, (p % cols * cw + 2, p // cols * ch + 2), im)
    sheet.save(os.path.join(args.out, "faces.png"))
    print(f"頭像 {PERSON_COUNT} 張、faces.png → {args.out}")

    plain = map_image(rom, rom.raw(MAP_BANK, 0x8000))
    plain.save(os.path.join(args.out, "map.png"))
    for k, year in enumerate(SCENARIO_YEARS):
        map_image(rom, rom.map_vram(k)).save(os.path.join(args.out, f"map_{year}.png"))
    cell = 1024 // TERRAIN_SIZE
    over = Image.new("RGB", (1024, 1024))
    for y in range(TERRAIN_SIZE):
        for x in range(TERRAIN_SIZE):
            over.paste(TERRAIN_COLOURS[rom.terrain(x, y)], (x * cell, y * cell, x * cell + cell, y * cell + cell))
    Image.blend(plain, over, 0.5).save(os.path.join(args.out, "terrain.png"))
    print(f"map.png、map_189.png、map_219.png、terrain.png → {args.out}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
