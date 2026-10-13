#!/usr/bin/env python3
"""匯出 SFC 三國志英傑伝的人物、道具、兵種、勢力、地點、戰鬥、頭像與地圖。

Usage: .venv/bin/python eiketsu/export.py [--rom ROM] [--out DIR]

Writes persons.csv, items.csv, classes.csv, forces.csv, terrains.csv, places.csv (4 lists with big-map
markers), npc_types.csv, battles.csv (58), battle_cells.csv (+ eiketsu.xlsx when openpyxl is installed),
faces/ (240 faces), map.png (the big map, 256 x 224), map_places.png (labelled, one per place list),
battle/ (the 58 battle maps) and font.png (the 1655 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, GLYPH_COUNT, ITEM_KINDS, PLACE_FILLER, WORLD_H, WORLD_W, Rom

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
PLACE_KINDS = {2: "関", 3: "城（推測）", 4: "庵・村（推測）"}


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([c or (0, 0, 0) for c in rgb])
    im.save(path)


def person_rows(rom: Rom) -> list[dict]:
    forces, classes, items = rom.forces(), rom.classes(), rom.items()
    rows = []
    for p in rom.persons():
        rows.append({"Id": p["id"], "姓名": p["name"], "読み": p["reading"], "頭像": p["face"],
                     "勢力": forces[p["force"]] if p["force"] < len(forces) else p["force"],
                     "武力": p["武力"], "統率": p["統率"], "知力": p["知力"],
                     "兵種": classes[p["class"]] if p["class"] < len(classes) else p["class"],
                     "持ち物": "、".join(items[i]["name"] if i < len(items) else str(i) for i in p["items"]),
                     "Unknown4": p["unknown4"], "Unknown6": p["unknown6"], "Unknown8(等級?)": p["unknown8"],
                     "Unknown15": p["unknown15"], "Flag": p["flag"]})
    return rows


def item_rows(rom: Rom) -> list[dict]:
    return [{"Id": i["id"], "名": i["name"], "種類": i["kind"], "種類名(推測)": ITEM_KINDS.get(i["kind"], ""),
             "価格": "" if i["price"] == 0xFF else i["price"], "Unknown15_19": i["unknown"]} for i in rom.items()]


def place_rows(rom: Rom) -> list[dict]:
    chapters = rom.chapter_groups()
    rows = []
    for g in range(1, 5):
        for p in rom.places(g):
            if p["name"] == PLACE_FILLER:
                continue
            rows.append({"組": g, "章": "、".join(str(c) for c, k in enumerate(chapters) if k == g), "Id": p["id"],
                         "名": p["name"], "読み": p["reading"], "種類": p["kind"],
                         "種類名": PLACE_KINDS.get(p["kind"], ""),
                         "地圖x(格)": p["marker"][0] if p["marker"] else "",
                         "地圖y(格)": p["marker"][1] if p["marker"] else ""})
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    names, titles = rom.battle_names(), rom.battle_titles()
    rows = []
    for n in range(len(names)):
        m = rom.battle_map(n)
        rows.append({"Id": n, "名": names[n], "標題": titles[n], "寬(格)": m["w"] // 2, "高(格)": m["h"] // 2,
                     "寬(16px)": m["w"], "高(16px)": m["h"], "圖塊組": m["set"]})
    return rows


def cell_rows(rom: Rom) -> list[dict]:
    terrains = rom.terrains()
    rows = []
    for n in range(58):
        for y, row in enumerate(rom.battle_map(n)["terrain"]):
            for x, t in enumerate(row):
                rows.append({"戰鬥": n, "x": x, "y": y, "地形": t,
                             "地形名(推測)": terrains[t] if t < len(terrains) else ""})
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
    w, h = WORLD_W * 8, WORLD_H * 8
    im = Image.new("RGB", (w, h))
    im.putdata(rom.world_rgb())
    im.save(os.path.join(out, "map.png"))
    scale = 4
    sheets = []
    f = font(14)
    for g in range(1, 5):
        big = im.resize((w * scale, h * scale), Image.NEAREST)
        dr = ImageDraw.Draw(big)
        for p in rom.places(g):
            if not p["marker"]:
                continue
            x, y = (v * 8 * scale for v in p["marker"])
            dr.rectangle([x, y, x + 8 * scale - 1, y + 8 * scale - 1], outline="red", width=3)
            dr.text((x + 8 * scale + 2, y + 4 * scale), f"{p['id']} {p['name']}", fill="white", anchor="lm", font=f,
                    stroke_width=2, stroke_fill="black")
        dr.text((8, 8), f"地點列表 {g}", fill="yellow", font=font(24), stroke_width=3, stroke_fill="black")
        sheets.append(big)
    sheet = Image.new("RGB", (w * scale * 2, h * scale * 2))
    for k, s in enumerate(sheets):
        sheet.paste(s, (k % 2 * w * scale, k // 2 * h * scale))
    sheet.save(os.path.join(out, "map_places.png"))


def battle_images(rom: Rom, out: str) -> None:
    d = os.path.join(out, "battle")
    os.makedirs(d, exist_ok=True)
    names = rom.battle_names()
    for n, name in enumerate(names):
        m = rom.battle_map(n)
        png(m["w"] * 16, m["h"] * 16, rom.battle_rgb(n), os.path.join(d, f"{n:02d}_{name}.png"))


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
    ap = argparse.ArgumentParser(description="匯出 SFC 三國志英傑伝資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "道具": item_rows(rom),
              "兵種": [{"Id": i, "名": n, "策略(Lv1)": a, "係數B(推測攻撃)": b, "係數C(推測防御)": c}
                     for i, (n, (a, b, c)) in enumerate(zip(rom.classes(), rom.class_params()))],
              "勢力": [{"Id": i, "名": n} for i, n in enumerate(rom.forces())],
              "地形": [{"Id": i, "名": n} for i, n in enumerate(rom.terrains())],
              "地點": place_rows(rom),
              "NPC": [{"Id": t["id"], "名": t["name"], "Unknown8": t["unknown"]} for t in rom.npc_types()],
              "戰鬥": battle_rows(rom), "戰場格": cell_rows(rom)}
    names = ("persons", "items", "classes", "forces", "terrains", "places", "npc_types", "battles", "battle_cells")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "eiketsu.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    for n in range(FACE_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(faces, f"{n:03d}.png"))
    map_images(rom, args.out)
    battle_images(rom, args.out)
    font_sheet(rom, os.path.join(args.out, "font.png"))
    print(f"頭像 {FACE_COUNT} 張、大地圖、戰場 {len(rom.battle_names())} 張、字型 → {args.out}")


if __name__ == "__main__":
    main()
