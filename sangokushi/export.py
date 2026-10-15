#!/usr/bin/env python3
"""匯出 SFC スーパー三國志 的劇本、人物、國、州、勢力、戰場、頭像、大地圖與字型。

Usage: .venv/bin/python sangokushi/export.py [--rom ROM] [--out DIR]

Writes scenarios.csv (5), persons.csv (255, name table + abilities), scenario_persons.csv (5 x 255),
countries.csv (58, static table + castle places), scenario_countries.csv (5 x 58), states.csv (15),
factions.csv (5 x the factions in play), battle_fields.csv (58), faces.csv (307 face codes)
(+ sangokushi.xlsx when openpyxl is installed), faces/ (one PNG per person), portraits/ (000-127),
composites/ (male 080-0FE, female 0FF-132), map.png (240 x 176), map_owners_1..5.png (owner colours of each
scenario, country numbers), battle/ (58 fields, 224 x 200, castles of the start) and font.png (921 glyphs).
"""
import argparse
import csv
import os
from collections import Counter

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BATTLE_GRID,
    BATTLE_TILEMAP,
    COMPOSITES,
    COUNTRY_COUNT,
    DEFAULT_ROM,
    FACE_H,
    FACE_PALETTE,
    FACE_W,
    GLYPH_COUNT,
    LAST_FACE,
    MAP_W,
    PERSON_STATS,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    TERRAIN,
    Rom,
    face_kind,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
KIND = {"portrait": "肖像", "male": "男性組合", "female": "女性組合"}


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([c or (0, 0, 0) for c in rgb])
    im.save(path)


def face_rgb(rom: Rom, code: int) -> list:
    pal = rom.palette_rgb(FACE_PALETTE)
    return [pal[v] for v in rom.face_pixels(code)]


def ruler_names(rom: Rom, sc: int, persons: list[dict]) -> dict[int, str]:
    return {f["id"]: persons[f["ruler"]]["name"] for f in rom.factions(sc) if f["ruler"]}


def scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in rom.scenarios():
        persons = rom.persons(s["id"])
        rulers = [persons[f["ruler"]]["name"] for f in rom.factions(s["id"]) if f["ruler"] and f["playable"]]
        rows.append({"Id": s["id"], "劇本": s["name"], "開始年": s["year"], "可選君主": "、".join(rulers),
                     "勢力數": sum(1 for f in rom.factions(s["id"]) if f["ruler"])})
    return rows


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.persons(1)[1:]:
        rows.append({"Id": p["id"], "姓名": p["name"], "讀音": p["reading"], "生年": p["born"],
                     **dict(zip(PERSON_STATS, p["stats"])), "頭像碼": f"{p['face']:04X}",
                     "頭像": KIND[face_kind(p["face"])]})
    return rows


def scenario_person_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in rom.scenarios():
        sc = s["id"]
        persons = rom.persons(sc)
        rulers = ruler_names(rom, sc, persons)
        ruler_ids = {f["ruler"] for f in rom.factions(sc) if f["ruler"]}
        governors = {k["governor"]: k["id"] for k in rom.countries(sc) if k["owner"]}
        for p in persons[1:]:
            f = p["faction"]
            rank = ("君主" if p["id"] in ruler_ids else "太守" if governors.get(p["id"]) == p["country"] and f
                    else "在野" if not f else "武將")
            rows.append({"劇本": sc, "Id": p["id"], "姓名": p["name"], "年齡": p["age"], "身分": rank,
                         "所屬(君主)": rulers.get(f, "") if f else "", "勢力Id": f, "所在國": p["country"],
                         **dict(zip(PERSON_STATS, p["stats"])),
                         "忠誠": "" if p["id"] in ruler_ids else p["loyalty"], "兵士": p["troops"],
                         "兵忠": p["morale"], "訓練": p["training"], "武装": p["arms"],
                         "水軍": "扱" if p["navy"] else "不", "旗標+7": f"{p['flags']:02X}",
                         "Unknown+15_17": p["raw"][15:18].hex(" ")})
    return rows


def country_rows(rom: Rom) -> list[dict]:
    rows = []
    for k in rom.countries(1):
        c = k["id"]
        rows.append({"國": c, "州": k["state_name"], "相鄰國": "、".join(map(str, k["neighbours"])),
                     "城位置(欄,列)": " ".join(f"{x},{y}" for x, y in rom.castle_cells(c)),
                     "Unknown旗標(靜態+1)": f"{k['flags']:02X}", "Unknown x(靜態+11)": k["x"],
                     "Unknown y(靜態+13)": k["y"]})
    return rows


def scenario_country_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in rom.scenarios():
        sc = s["id"]
        persons = rom.persons(sc)
        rulers = ruler_names(rom, sc, persons)
        for k in rom.countries(sc):
            r = k["raw"]
            rows.append({"劇本": sc, "國": k["id"], "州": k["state_name"],
                         "支配(君主)": rulers.get(k["owner"], "") if k["owner"] else "空白地", "勢力Id": k["owner"],
                         "太守": persons[k["governor"]]["name"] if k["owner"] else "", "太守Id": k["governor"],
                         "金": k["gold"], "兵糧": k["food"], "土地": k["land"], "洪水": k["flood"],
                         "治水(+7)": k["control"], "民忠": k["loyalty"], "人口": k["population"], "名馬": k["horses"],
                         "鉄": k["iron"], "城": k["castle"], "Unknown+0": k["w0"], "Unknown+13": k["b13"],
                         "Unknown+16": f"{k['b16']:02X}", "Unknown+17": f"{k['b17']:02X}",
                         "Unknown+18高4位": k["b18"], "Unknown+19": f"{k['b19']:02X}",
                         "Unknown+20_29": r[20:30].hex(" ")})
    return rows


def state_rows(rom: Rom) -> list[dict]:
    countries = rom.countries(1)
    return [{"Id": s["id"], "州": s["name"], "讀音": s["reading"],
             "國": "、".join(str(k["id"]) for k in countries if k["state"] == s["id"])} for s in rom.states()]


def faction_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in rom.scenarios():
        sc = s["id"]
        persons = rom.persons(sc)
        countries = rom.countries(sc)
        for f in rom.factions(sc):
            if not f["ruler"]:
                continue
            fid = f["id"]
            rows.append({"劇本": sc, "勢力Id": fid, "君主": persons[f["ruler"]]["name"], "君主Id": f["ruler"],
                         "可選": "○" if f["playable"] else "", "國數": sum(k["owner"] == fid for k in countries),
                         "武將數": sum(p["faction"] == fid for p in persons[1:]), "娘(+3)": f["daughters"],
                         "Unknown+2": f"{f['b2']:02X}",
                         "Unknown+7_20(對各勢力)": " ".join(f"{b:02X}" for b in f["relations"]),
                         "Unknown+4_6,+21_76": (f["raw"][4:7] + f["raw"][21:]).hex(" ")})
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for k in rom.countries(1):
        c = k["id"]
        cells = Counter(b >> 3 for row in rom.battle_grid(c, k["castle"]) for b in row)
        rows.append({"國": c, "州": k["state_name"], "地圖 LZ entry": BATTLE_TILEMAP + c - 1,
                     "格 LZ entry": BATTLE_GRID + c - 1, "開始時城數": k["castle"],
                     "城位置數": len(rom.castle_cells(c)), **{t: cells[i] for i, t in enumerate(TERRAIN)}})
    return rows


def face_rows(rom: Rom) -> list[dict]:
    users: dict[int, list[str]] = {}
    for n in rom.names()[1:]:
        users.setdefault(n["face"], []).append(n["name"])
    rows = []
    for code in range(LAST_FACE + 1):
        kind = face_kind(code)
        row = {"頭像碼": f"{code:04X}", "種類": KIND[kind], "使用者": "、".join(users.get(code, []))}
        if kind != "portrait":
            t, parts = rom.composite_record(code)
            row.update({"型": t, "部件": " ".join(map(str, parts))})
        rows.append(row)
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys, restval="")
        writer.writeheader()
        writer.writerows(rows)
    print(f"已匯出 {len(rows)} 筆 → {path}")


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        keys = list(dict.fromkeys(k for r in rows for k in r))
        ws.append(keys)
        for r in rows:
            ws.append([r.get(k, "") for k in keys])
        ws.freeze_panes = "B2"
    wb.save(path)
    print(f"已匯出 → {path}")


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def map_images(rom: Rom, out: str) -> None:
    w, h, rgb = rom.map_rgb()
    base = Image.new("RGB", (w, h))
    base.putdata(rgb)
    base.save(os.path.join(out, "map.png"))
    regions = rom.map_regions()
    centre = {}
    for c in range(1, COUNTRY_COUNT + 1):
        px = [i for i, v in enumerate(regions) if v == c]
        centre[c] = (sum(i % w for i in px) / len(px), sum(i // w for i in px) / len(px))
    scale = 4
    f = font(9 * scale // 2)
    for sc in range(1, SCENARIO_COUNT + 1):
        owners = [k["owner"] for k in rom.countries(sc)]
        _, _, layer = rom.map_owner_rgb(owners)
        im = base.copy()
        im.putdata([c if c else b for c, b in zip(layer, rgb)])
        im = im.resize((w * scale, h * scale), Image.NEAREST)
        dr = ImageDraw.Draw(im)
        for c, (x, y) in centre.items():
            dr.text((x * scale, y * scale), str(c), fill="white", anchor="mm", font=f, stroke_width=2,
                    stroke_fill="black")
        im.save(os.path.join(out, f"map_owners_{sc}.png"))


def battle_images(rom: Rom, out: str) -> None:
    d = os.path.join(out, "battle")
    os.makedirs(d, exist_ok=True)
    for k in rom.countries(1):
        w, h, rgb = rom.battle_rgb(k["id"], k["castle"])
        png(w, h, rgb, os.path.join(d, f"{k['id']:02d}_{k['state_name']}.png"))


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
    ap = argparse.ArgumentParser(description="匯出 SFC スーパー三國志 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"劇本": scenario_rows(rom), "人物": person_rows(rom), "劇本人物": scenario_person_rows(rom),
              "國": country_rows(rom), "劇本國": scenario_country_rows(rom), "州": state_rows(rom),
              "勢力": faction_rows(rom), "戰場": battle_rows(rom), "頭像": face_rows(rom)}
    names = ("scenarios", "persons", "scenario_persons", "countries", "scenario_countries", "states", "factions",
             "battle_fields", "faces")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "sangokushi.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    fw, fh = FACE_W * 8, FACE_H * 8
    dirs = {k: os.path.join(args.out, k) for k in ("faces", "portraits", "composites")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    for n in rom.names()[1:]:
        png(fw, fh, face_rgb(rom, n["face"]), os.path.join(dirs["faces"], f"{n['id']:03d}_{n['name']}.png"))
    for code in range(LAST_FACE + 1):
        kind = face_kind(code)
        name = f"{code:03d}.png" if kind == "portrait" else f"{kind}_{code:03X}.png"
        png(fw, fh, face_rgb(rom, code), os.path.join(dirs["portraits" if kind == "portrait" else "composites"], name))
    map_images(rom, args.out)
    battle_images(rom, args.out)
    font_sheet(rom, os.path.join(args.out, "font.png"))
    n_comp = sum(c[1] for c in COMPOSITES.values())
    print(f"頭像 255 人＋肖像 {PORTRAIT_COUNT}＋組合 {n_comp}、大地圖（{MAP_W * 8} 寬）、戰場 {COUNTRY_COUNT} 張、字型 → "
          f"{args.out}")


if __name__ == "__main__":
    main()
