#!/usr/bin/env python3
"""Export SFC スーパー信長の野望・全国版: persons, scenario daimyo, provinces, scenarios, battle maps, faces and maps.

Usage: .venv/bin/python zenkoku/export.py [--rom ROM] [--out DIR]

Writes scenarios.csv, persons.csv (68 person ids), daimyo_scenarios.csv (4 scenarios), provinces.csv (50 + 17
provinces), province_scenarios.csv, battle_maps.csv, battle_cells.csv (+ zenkoku.xlsx when openpyxl is installed),
faces/ (one PNG per person), portraits/ (000-072), map_50.png / map_17.png (unpainted), map_scenario1-4.png
(painted with the owners' patterns as the game shows them at the start), map_50_labelled.png, battle/ (50 maps)
and font.png (the 636 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BATTLE_COUNT,
    BATTLE_H,
    BATTLE_W,
    DAIMYO_STATS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    GLYPH_COUNT,
    MAP_H,
    MAP_W,
    PERSON_COUNT,
    PORTRAIT_COUNT,
    PORTRAIT_FIRST,
    PROVINCE_FIELDS,
    SCENARIO_COUNT,
    TERRAIN,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing


def png(w: int, h: int, rgb: list, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def scenario_rows(rom: Rom) -> list[dict]:
    return [{"劇本": s + 1, "標題": t.split(" (")[0], "開始年": rom.scenario_year(s), "國數": rom.province_count(s),
             "大名數": rom.scenario_daimyo_count(s)} for s, t in enumerate(rom.scenario_titles())]


def person_rows(rom: Rom) -> list[dict]:
    return [{"Id": p["id"], "姓名": p["name"], "姓": p["surname"], "名": p["given"],
             "登場劇本": "、".join(map(str, p["scenarios"])), "頭像(LZ)": PORTRAIT_FIRST + p["id"]}
            for p in rom.persons()]


def daimyo_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        names = rom.province_names(s)
        for d in rom.daimyos(s):
            rows.append({"劇本": s + 1, "Slot": d["index"], "Id": d["person"], "姓名": d["name"], "年齢": d["age"],
                         **{ja: d[k] for k, ja in DAIMYO_STATS}, "花紋": d["pattern"],
                         "領國數": len(d["provinces"]), "領國": "、".join(names[p] for p in d["provinces"]),
                         "Byte7": d["byte7"]})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    rows = []
    to50 = rom.mode17_province()
    for s, mode in ((1, 50), (0, 17)):
        names, seeds = rom.province_names(s), rom.map_seeds(mode)
        names50 = rom.province_names(1)
        for p in rom.provinces(s):
            i = p["index"]
            rows.append({"模式": mode, "Id": i, "國名": names[i], "地方(1-7)": p["region"],
                         "相鄰": "、".join(names[n] for n in p["neighbours"]),
                         "戰場地圖": i if mode == 50 else to50[i],
                         "戰場地圖的國(50國)": names50[i if mode == 50 else to50[i]],
                         "上色起點x": seeds[i][0], "上色起點y": seeds[i][1]})
    return rows


def province_scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        daimyo = {d["index"]: d["name"] for d in rom.daimyos(s)}
        for p in rom.provinces(s):
            rows.append({"劇本": s + 1, "Id": p["index"], "國名": p["name"], "大名": daimyo.get(p["owner"], ""),
                         **{(ja or k): p[k] for k, ja in PROVINCE_FIELDS}, "Unknown312E": p["unk312E"]})
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    names50, names17 = rom.province_names(1), rom.province_names(0)
    to50 = rom.mode17_province()
    rows = []
    for m in range(BATTLE_COUNT):
        cells = rom.battle_cells(m)
        count = {v: sum(1 for c in cells if c == k) for k, (_, v) in TERRAIN.items()}
        rows.append({"Id": m, "國(50國)": names50[m],
                     "17國模式使用": "、".join(names17[i] for i, t in enumerate(to50) if t == m),
                     **{f"{v}格數": n for v, n in count.items()}})
    return rows


def cell_rows(rom: Rom) -> list[dict]:
    rows = []
    for m in range(BATTLE_COUNT):
        cells = rom.battle_cells(m)
        for r in range(BATTLE_H):
            for c in range(BATTLE_W):
                v = cells[r * BATTLE_W + c]
                rows.append({"地圖": m, "列(x)": c, "行(y)": r, "地形(hex)": f"{v:02X}",
                             "地形": TERRAIN.get(v, ("", "?"))[1]})
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


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def map_images(rom: Rom, out: str) -> None:
    w, h = MAP_W * 8, MAP_H * 8
    for mode in (50, 17):
        png(*rom.map_rgb(None, mode), os.path.join(out, f"map_{mode}.png"), 2)
    for s in range(SCENARIO_COUNT):
        png(*rom.map_rgb(s), os.path.join(out, f"map_scenario{s + 1}.png"), 2)
    # labelled 50-province map: seed points (the game's paint start) with id and name
    im = Image.new("RGB", (w, h))
    im.putdata(rom.map_rgb(1)[2])
    big = im.resize((w * 4, h * 4), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    f = font(16)
    names = rom.province_names(1)
    for p, (x, y) in enumerate(rom.map_seeds(50)):
        dr.ellipse([4 * x - 4, 4 * y - 4, 4 * x + 4, 4 * y + 4], fill="red")
        dr.text((4 * x + 6, 4 * y), f"{p} {names[p]}", fill="white", anchor="lm", font=f, stroke_width=2,
                stroke_fill="black")
    big.save(os.path.join(out, "map_50_labelled.png"))


def font_sheet(rom: Rom, path: str) -> None:
    cols = 32
    rows = (GLYPH_COUNT + cols - 1) // cols
    im = Image.new("L", (cols * 17, rows * 17), 255)
    px = im.load()
    for g in range(GLYPH_COUNT):
        gx, gy = g % cols * 17, g // cols * 17
        for y, row in enumerate(rom.glyph(g)):
            for x, v in enumerate(row):
                if v:
                    px[gx + x, gy + y] = 0
    im.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 信長の野望・全国版資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"劇本": scenario_rows(rom), "人物": person_rows(rom), "劇本大名": daimyo_rows(rom),
              "國": province_rows(rom), "劇本國": province_scenario_rows(rom), "戰場": battle_rows(rom),
              "戰場格": cell_rows(rom)}
    names = ("scenarios", "persons", "daimyo_scenarios", "provinces", "province_scenarios", "battle_maps",
             "battle_cells")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "zenkoku.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    persons = rom.persons()
    for p in persons:
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["id"]), os.path.join(faces, f"{p['id']:03d}_{p['name']}.png"))
    for n in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"{n:03d}.png"))
    map_images(rom, args.out)
    d = os.path.join(args.out, "battle")
    os.makedirs(d, exist_ok=True)
    names50 = rom.province_names(1)
    for m in range(BATTLE_COUNT):
        png(*rom.battle_rgb(m), os.path.join(d, f"{m:02d}_{names50[m]}.png"))
    font_sheet(rom, os.path.join(args.out, "font.png"))
    assert len(persons) == PERSON_COUNT
    print(f"頭像 {len(persons)} 人＋{PORTRAIT_COUNT} 張、大地圖、戰場 {BATTLE_COUNT} 張、字型 → {args.out}")


if __name__ == "__main__":
    main()
