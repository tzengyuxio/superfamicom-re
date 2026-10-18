#!/usr/bin/env python3
"""匯出 SFC 横山光輝 三国志2 的人物、劇本、國、勢力、頭像與大地圖。

Usage: .venv/bin/python yokoyama2/export.py [--rom ROM] [--out DIR]

Writes persons.csv (229), scenario_persons.csv (3 x 229: placement and all fields), countries.csv (35),
scenario_countries.csv (3 x 35, with 金 / 米 of the three difficulties), factions.csv (3 scenarios)
(+ yokoyama2.xlsx when openpyxl is installed), faces/ (229 PNG) and faces.png (all of them on one sheet),
map.png (1024 x 1024) and map_189.png / map_200.png / map_215.png (with the country markers in faction colours).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw
from rom import (
    COUNTRY_COUNT,
    DEFAULT_ROM,
    DIFFICULTIES,
    FACE_H,
    FACE_W,
    FACTION_COUNT,
    KANI,
    PERSON_COUNT,
    PLACE_KINDS,
    SCENARIO_YEARS,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PERSON_COLUMNS = ["レベル", "経験値", "体力", "武力", "兵法力", "政治力", "統率力", "忠誠度", "人望", "士気", "疲労度",
                  "兵士数", "移動力"]
MARKER = 24                 # marker square on the 1024 x 1024 map (the game's 8 x 8 sprite is 32 map pixels)


def place_text(rom: Rom, k: int, p: int) -> dict:
    kind, country, ref, year, _ = rom.place(k, p)
    who = rom.name(ref) if kind in (2, 4, 5) and ref < PERSON_COUNT else ""
    faction = rom.name(rom.rulers(k)[ref]) + "軍" if kind == 3 and ref < FACTION_COUNT else ""
    return {"配置": PLACE_KINDS.get(kind, f"{kind:02X}"),
            "國": rom.country_name(country) if kind in (0, 1, 3, 4, 5) and country < COUNTRY_COUNT else "",
            "關係人物": who or faction, "登場年": year if kind in (1, 2, 3, 4, 5) else "",
            "配置(原始)": rom.place(k, p).hex(" ").upper()}


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in range(PERSON_COUNT):
        row = {"Id": p, "名前": rom.name(p), "読み": rom.reading(p), "頭像部品": rom.face_parts(p).hex(" ").upper()}
        for k, year in enumerate(SCENARIO_YEARS):
            pl = place_text(rom, k, p)
            row[f"{year}配置"] = pl["配置"] + (f"（{pl['國']}）" if pl["國"] else "")
        rows.append(row)
    return rows


def scenario_person_rows(rom: Rom) -> list[dict]:
    rows = []
    for k, year in enumerate(SCENARIO_YEARS):
        heads = rom.scenario_wram(k)[0x0700]
        for p in range(PERSON_COUNT):
            v = rom.person(k, p)
            h = heads[24 * p]
            row = {"劇本": year, "Id": p, "名前": rom.name(p), **place_text(rom, k, p),
                   "勢力": rom.name(rom.rulers(k)[h & 0x0F]) + "軍" if h & 0x80 else "",
                   "官位": KANI.get(v["官位"], f"{v['官位']:02X}")}
            row.update({c: v[c] for c in PERSON_COLUMNS})
            row["攻撃力"] = v["武力"] + v["士気"]
            row.update({"騎": v["武器"] & 15, "弓": v["武器"] >> 4, "歩": v["武器2"]})
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
            governor = v.pop("太守")
            row = {"劇本": year, "Id": c, "國名": rom.country_name(c),
                   "勢力": rom.name(rom.rulers(k)[f]) + "軍" if f != 0xFF else "",
                   "太守": rom.name(governor) if f != 0xFF else ""}
            v["民"] *= 1000
            row.update(v)
            for d, name in enumerate(DIFFICULTIES):
                if d != 1:
                    row[f"金({name})"], row[f"米({name})"] = rom.gold_food(k, d, c)
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
            officers = sum(h & 0x80 and h & 0x0F == f for h in rom.scenario_wram(k)[0x0700][::24])
            rows.append({"劇本": year, "勢力": f, "君主": rom.name(r), "國數": len(countries), "武將數": officers,
                         "國": "、".join(countries)})
    return rows


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


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 横山光輝 三国志2 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "劇本人物": scenario_person_rows(rom), "國": country_rows(rom),
              "劇本國": scenario_country_rows(rom), "勢力": faction_rows(rom)}
    names = ("persons", "scenario_persons", "countries", "scenario_countries", "factions")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "yokoyama2.xlsx"))
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

    plain = Image.new("P", (1024, 1024))
    plain.putdata(rom.map_image_pixels(rom.map_vram()))
    plain.putpalette([v for c in rom.map_palette() for v in c])
    plain = plain.convert("RGB")
    plain.save(os.path.join(args.out, "map.png"))
    for k, year in enumerate(SCENARIO_YEARS):
        im = plain.copy()
        dr = ImageDraw.Draw(im)
        for c in range(COUNTRY_COUNT):
            x, y = rom.position(c)
            cx, cy = 16 * x + 8, 16 * y + 8
            colour = rom.marker(rom.country(k, c)["勢力"])[2]
            dr.rectangle([cx - MARKER // 2, cy - MARKER // 2, cx + MARKER // 2, cy + MARKER // 2], fill=colour,
                         outline=(0, 0, 0), width=3)
        im.save(os.path.join(args.out, f"map_{year}.png"))
    print("map.png、" + "、".join(f"map_{y}.png" for y in SCENARIO_YEARS) + f" → {args.out}")


if __name__ == "__main__":
    main()
