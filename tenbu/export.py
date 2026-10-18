#!/usr/bin/env python3
"""匯出 SFC 三国志正史 天舞スピリッツ 的人物、勢力、郡国、名稱表、頭像與地圖（解碼尚未全部經 Mesen 驗證，見 README）。

Usage: .venv/bin/python tenbu/export.py [--rom ROM] [--out DIR]

Writes scenario_persons.csv (4 x 600), factions.csv, provinces.csv (126), scenario_provinces.csv (4 x 126),
offices.csv (48), names.csv (州 / 異民族 / 王号) (+ tenbu.xlsx when openpyxl is installed), faces/ (250 PNG) and
faces.png, map.png (local map 2160 x 1840), region.png (中国全土図 248 x 224), charset.png (font glyphs).
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    DEFAULT_ROM,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    FACTION_COUNT,
    GLYPH_BASE,
    KANJI_COUNT,
    MAP_H,
    MAP_W,
    OFFICE_COUNT,
    PERSON_COUNT,
    PROVINCE_COUNT,
    REGION_H,
    REGION_W,
    SCENARIO_YEARS,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def ruler_name(rom: Rom, k: int, f: int) -> str:
    v = rom.faction(k, f) if f < FACTION_COUNT else None
    return rom.person(k, v["君主"])["名前"] if v else ""


def scenario_person_rows(rom: Rom) -> list[dict]:
    rows = []
    for k, year in enumerate(SCENARIO_YEARS):
        for p in range(PERSON_COUNT):
            v = rom.person(k, p)
            row = {"劇本": year, "Id": p, **v}
            row["勢力名"] = ruler_name(rom, k, v["勢力"])
            row["所在名"] = rom.province_name(v["所在"]) if v["所在"] < PROVINCE_COUNT else ""
            row["血縁名"] = rom.person(k, v["血縁"])["名前"] if v["血縁"] < PERSON_COUNT else ""
            row["官職名"] = rom.office(v["官職"])[0].rstrip("　") if v["官職"] < OFFICE_COUNT else ""
            row["原始"] = rom.person_raw(k, p).hex(" ").upper()
            rows.append(row)
    return rows


def faction_rows(rom: Rom) -> list[dict]:
    rows = []
    for k, year in enumerate(SCENARIO_YEARS):
        for f in range(FACTION_COUNT):
            v = rom.faction(k, f)
            if v:
                rel = v.pop("関係")
                rows.append({"劇本": year, "Id": f, **v, "君主名": rom.person(k, v["君主"])["名前"],
                             "郡国數": sum(rom.province(k, c)["勢力"] == f for c in range(PROVINCE_COUNT)),
                             "関係": " ".join(map(str, rel)), "原始": rom.faction_raw(k, f).hex(" ").upper()})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    return [{"Id": c, "郡国名": rom.province_name(c), "読み": rom.province_reading(c),
             "X": rom.province_pos(c)[0], "Y": rom.province_pos(c)[1]} for c in range(PROVINCE_COUNT)]


def scenario_province_rows(rom: Rom) -> list[dict]:
    rows = []
    for k, year in enumerate(SCENARIO_YEARS):
        for c in range(PROVINCE_COUNT):
            v = rom.province(k, c)
            rows.append({"劇本": year, "Id": c, "郡国名": rom.province_name(c), **v, "人口": v["人口/100"] * 100,
                         "勢力名": ruler_name(rom, k, v["勢力"]),
                         "太名": rom.person(k, v["太"])["名前"] if v["太"] < PERSON_COUNT else "",
                         "原始": rom.province_raw(k, c).hex(" ").upper()})
    return rows


def office_rows(rom: Rom) -> list[dict]:
    rows = []
    for n in range(OFFICE_COUNT):
        name, modern, extra = rom.office(n)
        rows.append({"Id": n, "官職": name.rstrip("　"), "現代名": modern.rstrip("　"), "後續2byte": extra.hex(" ")})
    return rows


def name_rows(rom: Rom) -> list[dict]:
    rows = [{"表": "州", "Id": i, "名稱": s} for i, s in enumerate(rom.states())]
    rows += [{"表": "異民族", "Id": i, "名稱": s} for i, s in enumerate(rom.peoples())]
    rows += [{"表": "王号", "Id": i, "名稱": s} for i, s in enumerate(rom.kingdoms())]
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


def indexed(px: list[int], pal: list, w: int, h: int) -> Image.Image:
    im = Image.new("P", (w, h))
    im.putdata(px)
    im.putpalette([v for c in pal for v in c])
    return im.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 三国志正史 天舞スピリッツ 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"劇本人物": scenario_person_rows(rom), "勢力": faction_rows(rom), "郡国": province_rows(rom),
              "劇本郡国": scenario_province_rows(rom), "官職": office_rows(rom), "名稱表": name_rows(rom)}
    names = ("scenario_persons", "factions", "provinces", "scenario_provinces", "offices", "names")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "tenbu.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    cols, cw, ch = 16, FACE_W + 4, FACE_H + 4
    sheet = Image.new("RGB", (cols * cw, (FACE_COUNT + cols - 1) // cols * ch), (40, 40, 40))
    for n in range(FACE_COUNT):
        im = Image.new("RGBA", (FACE_W, FACE_H))
        im.putdata([(*c, 255) if c else (0, 0, 0, 0) for c in rom.face_rgb(n)])
        im.save(os.path.join(faces, f"{n:03d}.png"))
        sheet.paste(im, (n % cols * cw + 2, n // cols * ch + 2), im)
    sheet.save(os.path.join(args.out, "faces.png"))
    print(f"頭像 {FACE_COUNT} 張、faces.png → {args.out}")

    indexed(*rom.local_map(), MAP_W * 8, MAP_H * 8).save(os.path.join(args.out, "map.png"))
    indexed(*rom.region_map(), REGION_W * 8, REGION_H * 8).save(os.path.join(args.out, "region.png"))

    total = GLYPH_BASE + KANJI_COUNT
    font = Image.new("L", (32 * 18, (total + 31) // 32 * 18), 255)
    for g in range(total):
        px = rom.glyph(g)
        im = Image.new("L", (16, 16))
        im.putdata([255 - v * 255 if g >= 0x48 else 255 - v * 16 for v in px])
        font.paste(im, (g % 32 * 18 + 1, g // 32 * 18 + 1))
    font.save(os.path.join(args.out, "charset.png"))
    print(f"map.png、region.png、charset.png → {args.out}")


if __name__ == "__main__":
    main()
