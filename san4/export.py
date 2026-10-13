#!/usr/bin/env python3
"""匯出 SFC 三國志IV 的人物、劇本人物、都市、勢力、戰場、頭像與地圖。

Usage: .venv/bin/python san4/export.py [--rom ROM] [--out DIR]

Writes persons.csv, person_scenarios.csv (6 scenarios), cities.csv (43 cities), city_scenarios.csv,
forces.csv, abilities.csv, battle_maps.csv, battle_cells.csv (+ san4.xlsx when openpyxl is installed),
faces/ (one PNG per person), portraits/ (000-338), map.png (the big map, 1024 x 768), map_cities.png
(labelled), battle/ (the 88 battle maps, palette set 3 = month 12) and font.png (the 1997 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BATTLE_TILES_H,
    BATTLE_TILES_W,
    CITY_LISTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    GLYPH_COUNT,
    MAP_H,
    MAP_W,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    STATS,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([c or (0, 0, 0) for c in rgb])
    im.save(path)


def abilities_text(rom: Rom, bits: int) -> str:
    names = rom.abilities()
    out = [names[b] for b in sorted(names) if bits >> b & 1]
    out += [f"bit{b}" for b in range(32) if bits >> b & 1 and b not in names]
    return "、".join(out)


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.persons():
        code = p["face"]
        rows.append({"Id": p["id"], "ROM_Offset": f"0x{p['offset']:05X}", "姓名": p["name"], "読み": p["reading"],
                     "生年": p["born"], **{s: p[s] for s in STATS},
                     "頭像碼": f"{code:04X}", "頭像": f"組合 包{code & 15}" if code & 0x8000 else f"專屬 {code:03d}",
                     "關係": "" if p["relation"] == 0xFFFF else p["relation"], "相性(推測)": p["compat"],
                     "Unknown26": p["unknown26"], "Unknown27_29": p["unknown27"]})
    return rows


def scenario_rows(rom: Rom) -> list[dict]:
    persons, cities, titles = rom.persons(), rom.cities(), rom.scenario_titles()
    rows = []
    for sc in range(SCENARIO_COUNT):
        sp, forces = rom.scenario_persons(sc), rom.scenario_forces(sc)
        members = rom.scenario_members(sc)
        rulers = {f["ruler"]: f["id"] for f in forces if f["ruler"] != 0xFFFF}
        governors = {c["governor"] for c in rom.scenario_cities(sc)}
        ruler_name = {f["id"]: persons[sp[f["ruler"] - 1]["person"]]["name"] for f in forces if f["ruler"] != 0xFFFF}
        year = titles[sc]["year"]
        for s in sp:
            p = persons[s["person"]]
            lst = CITY_LISTS.get(members.get(s["no"], (0, 0))[1], "")
            rank = "君主" if s["no"] in rulers else "太守" if s["no"] in governors else lst
            rows.append({"劇本": sc + 1, "年": year, "記錄": s["no"], "Id": s["person"], "姓名": p["name"],
                         "年齢": year - p["born"], "勢力": ruler_name.get(s["force"], "") if s["force"] != 0xFF else "",
                         "身分": rank, "所在": cities[s["city"]]["name"] if s["city"] < len(cities) else s["city"],
                         "忠誠": s["loyalty"], **{st: p[st] for st in STATS},
                         "特殊能力": abilities_text(rom, s["abilities"]), "特殊能力(hex)": f"{s['abilities']:08X}",
                         "Unknown2_5": s["unknown2"], "Unknown13": f"{s['unknown13']:04X}"})
    return rows


def city_rows(rom: Rom) -> list[dict]:
    cities = rom.cities()
    return [{"Id": c["id"], "名": c["name"], "読み": c["reading"], "地圖x(格)": c["map_x"], "地圖y(格)": c["map_y"],
             "相鄰": "、".join(cities[n]["name"] for n in c["neighbours"]), "Unknown0": c["unknown0"],
             "Unknown1": c["unknown1"], "Flags": f"{c['flags']:02X}"} for c in cities]


def city_scenario_rows(rom: Rom) -> list[dict]:
    persons, cities = rom.persons(), rom.cities()
    rows = []
    for sc in range(SCENARIO_COUNT):
        sp, forces = rom.scenario_persons(sc), rom.scenario_forces(sc)
        ruler_name = {f["id"]: persons[sp[f["ruler"] - 1]["person"]]["name"] for f in forces if f["ruler"] != 0xFFFF}
        for c in rom.scenario_cities(sc):
            g = c["governor"]
            rows.append({"劇本": sc + 1, "Id": c["id"], "名": cities[c["id"]]["name"],
                         "勢力": ruler_name.get(c["owner"], "") if c["owner"] != 0xFF else "",
                         "太守": persons[sp[g - 1]["person"]]["name"] if g != 0xFFFF else "",
                         "人口": c["population"], "金": c["gold"], "兵糧": c["food"], "兵士": c["soldiers"],
                         "開発": c["develop"], "治水": c["flood"], "商業": c["commerce"], "技術": c["tech"],
                         "民忠": c["loyalty"], "士気": c["morale"], "訓練": c["training"], "弩": c["crossbow"],
                         "強弩": c["strong_crossbow"], "連弩": c["repeating_crossbow"], "軍馬": c["horses"],
                         "発石": c["catapult"], "Unknown28": c["unknown28"]})
    return rows


def force_rows(rom: Rom) -> list[dict]:
    persons, cities = rom.persons(), rom.cities()
    rows = []
    for sc in range(SCENARIO_COUNT):
        sp = rom.scenario_persons(sc)
        forces = rom.scenario_forces(sc)
        name = {f["id"]: persons[sp[f["ruler"] - 1]["person"]]["name"] for f in forces if f["ruler"] != 0xFFFF}
        for f in forces:
            if f["ruler"] == 0xFFFF:
                continue
            rows.append({"劇本": sc + 1, "Id": f["id"], "君主": name[f["id"]],
                         "本拠(君主所在)": cities[f["seat"]]["name"] if f["seat"] < len(cities) else "",
                         "都市數": len(f["cities"]), "都市": "、".join(cities[c]["name"] for c in f["cities"]),
                         "Unknown8": f["unknown8"],
                         "友好度": " ".join(f"{name[k]}:{v}" for k, v in enumerate(f["friendship"])
                                          if k in name and k != f["id"])})
    return rows


def ability_rows(rom: Rom) -> list[dict]:
    return [{"bit": b, "名": n} for b, n in sorted(rom.abilities().items())]


def battle_rows(rom: Rom, maps: list[dict]) -> list[dict]:
    cities = rom.cities()
    rows = []
    for m in maps:
        uses = "、".join(f"{cities[a]['name']}→{cities[t]['name']}" for t, a in m["uses"])
        rows.append({"Id": m["id"], "種類": "野戦" if m["kind"] == "field" else "攻城",
                     "都市": cities[m["city"]]["name"] if m["city"] is not None else "", "使用(攻方→守方)": uses})
    return rows


def cell_rows(maps: list[dict]) -> list[dict]:
    rows = []
    for m in maps:
        for r, (dep, ter) in enumerate(zip(m["deploy"], m["terrain"])):
            for c in range(len(dep)):
                if c % 2 and r == len(m["deploy"]) - 1:
                    continue  # odd columns have 10 cells
                rows.append({"地圖": m["id"], "列(x)": c, "行(y)": r, "地形(hex)": f"{ter[c]:02X}",
                             "配置": "" if dep[c] == 0xFF else dep[c]})
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
    im = Image.new("RGB", (w, h))
    im.putdata(rom.map_rgb())
    im.save(os.path.join(out, "map.png"))
    big = im.resize((w * 2, h * 2), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    cities = rom.cities()
    f = font(20)
    for c in cities:
        cx, cy = c["map_x"] * 16 + 16, c["map_y"] * 16 + 16
        for n in c["neighbours"]:
            if n > c["id"]:
                d = cities[n]
                dr.line([cx, cy, d["map_x"] * 16 + 16, d["map_y"] * 16 + 16], fill=(255, 220, 0), width=2)
    for c in cities:
        x, y = c["map_x"] * 16, c["map_y"] * 16
        dr.rectangle([x, y, x + 31, y + 31], outline="red", width=3)
        dr.text((x + 36, y + 16), f"{c['id']} {c['name']}", fill="white", anchor="lm", font=f, stroke_width=3,
                stroke_fill="black")
    big.save(os.path.join(out, "map_cities.png"))


def battle_images(rom: Rom, maps: list[dict], out: str) -> None:
    d = os.path.join(out, "battle")
    os.makedirs(d, exist_ok=True)
    cities = rom.cities()
    for m in maps:
        tag = f"siege_{cities[m['city']]['name']}" if m["city"] is not None else "field"
        png(BATTLE_TILES_W * 8, BATTLE_TILES_H * 8, rom.battle_rgb(m["id"]), os.path.join(d, f"{m['id']:02d}_{tag}.png"))


def font_sheet(rom: Rom, path: str) -> None:
    cols = 64
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
    ap = argparse.ArgumentParser(description="匯出 SFC 三國志IV 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    maps = rom.battle_maps()

    sheets = {"人物": person_rows(rom), "劇本人物": scenario_rows(rom), "都市": city_rows(rom),
              "劇本都市": city_scenario_rows(rom), "勢力": force_rows(rom), "特殊能力": ability_rows(rom),
              "戰場": battle_rows(rom, maps), "戰場格": cell_rows(maps)}
    names = ("persons", "person_scenarios", "cities", "city_scenarios", "forces", "abilities", "battle_maps",
             "battle_cells")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "san4.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p in rom.persons():
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["face"]), os.path.join(faces, f"{p['id']:03d}_{p['name']}.png"))
    for n in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"{n:03d}.png"))
    map_images(rom, args.out)
    battle_images(rom, maps, args.out)
    font_sheet(rom, os.path.join(args.out, "font.png"))
    print(f"頭像 {len(rom.persons())} 人＋{PORTRAIT_COUNT} 張、大地圖、戰場 {len(maps)} 張、字型 → {args.out}")


if __name__ == "__main__":
    main()
