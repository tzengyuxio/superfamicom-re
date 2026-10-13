#!/usr/bin/env python3
"""匯出 SFC 三國志III 的人物、劇本、州、勢力、寶物、頭像與地圖。

Usage: .venv/bin/python san3/export.py [--rom ROM] [--out DIR]

Writes persons.csv, person_scenarios.csv, provinces.csv, province_scenarios.csv, factions.csv, items.csv,
scenarios.csv (+ san3.xlsx when openpyxl is installed), faces/ (one PNG per person), portraits/ (P001-P307),
composite_parts.png, map.png, map_provinces.png, map_scenario1-6.png and tactical/ (battlefield layers).
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from rom import (
    COMPOSITE_TYPES,
    DEFAULT_ROM,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    MAP_H,
    MAP_W,
    NONE16,
    PART_VARIANTS,
    PROVINCE_COUNT,
    SCENARIO_COUNT,
    TACTICAL_ENTRY,
    TACTICAL_W,
    Rom,
    bgr555_rgb,
    decode_tile,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
ITEM_KINDS = {0: "書", 1: "武器", 2: "馬", 3: "医書", 4: "玉璽"}


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def png(w: int, h: int, rgb: list[tuple[int, int, int]], path: str, scale: int = 1) -> Image.Image:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    if path:
        im.save(path)
    return im


def face_label(face: int) -> str:
    return f"C{face:04X}" if face & 0x8000 else f"P{face:03d}"


class Context:
    """Lookups shared by the sheets."""

    def __init__(self, rom: Rom):
        self.rom = rom
        self.persons = rom.persons()
        self.provinces = rom.provinces()
        self.ranks = rom.rank_labels()
        self.titles = rom.scenario_titles()
        self.items = rom.items()

    def person(self, pid: int) -> str:
        return self.persons[pid]["name"] if pid < len(self.persons) else ("" if pid == NONE16 else f"#{pid}")

    def province(self, k: int) -> str:
        return self.provinces[k]["name"] if k < PROVINCE_COUNT else ""

    def rulers(self, sc: int) -> dict[int, str]:
        return {f["id"]: self.person(f["ruler"]) for f in self.rom.scenario_factions(sc) if f["ruler"] != NONE16}


def person_rows(cx: Context) -> list[dict]:
    rows = []
    for p in cx.persons:
        rows.append({"Id": p["id"], "ROM_Offset": f"0x{p['offset']:05X}", "姓名": p["name"], "読み": p["reading"],
                     "生年": p["born"], "頭像": face_label(p["face"]), "陸指": p["land"], "水指": p["water"],
                     "武力": p["war"], "智力": p["int"], "政治": p["pol"], "魅力": p["cha"], "野心": p["ambition"],
                     "運": p["luck"], "冷静": p["calm"], "勇猛": p["bravery"], "相性": p["affinity"], "義理": p["duty"],
                     "血縁": "" if p["kin"] == 0xFF else p["kin"], "Unknown_3": p["unknown3"],
                     "Unknown_4": f"0x{p['flags4']:02X}"})
    return rows


def person_scenario_rows(cx: Context) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        year = cx.rom.scenario_header(sc)["year"]
        pf = cx.rom.province_factions(sc)
        provs = cx.rom.scenario_provinces(sc)
        rulers = cx.rulers(sc)
        owners = {it["owners"][sc]: [] for it in cx.items}
        for it in cx.items:
            owners[it["owners"][sc]].append(it["name"])
        for sp in cx.rom.scenario_persons(sc):
            p = cx.persons[sp["id"]]
            absent = sp["rank_byte"] == 0xFF
            rank = sp["rank"]
            faction = pf.get(sp["province"], 0xFF) if not absent and rank <= 4 else 0xFF
            troops = not absent and rank < 4 and sp["soldiers"] != 0
            prov = provs[sp["province"]] if troops else None
            rows.append({
                "劇本": sc + 1, "年": year, "Id": sp["id"], "姓名": p["name"],
                "登場": "" if absent else "○", "年齢": year - p["born"] + 1,
                "身分": "" if absent else (cx.ranks[rank] if rank < len(cx.ranks) else rank),
                "身分_raw": f"0x{sp['rank_byte']:02X}", "勢力": rulers.get(faction, ""),
                "所在": cx.province(sp["province"]), "忠誠": "" if sp["loyalty"] == 0xFF else sp["loyalty"],
                "兵士": "" if sp["raw"][0] == 0xFF else sp["soldiers"],
                "訓練": prov["training"] if prov else "", "士気": prov["morale"] if prov else "",
                "寶物": "、".join(owners.get(sp["id"], [])),
            })
    return rows


def province_rows(cx: Context) -> list[dict]:
    cells = cx.rom.map_cells()
    return [{"Id": p["id"], "ROM_Offset": f"0x{p['offset']:05X}", "名": p["name"], "読み": p["reading"],
             "地圖_x": cells[p["id"] - 1][0], "地圖_y": cells[p["id"] - 1][1], "Unknown_0": p["b0"], "Unknown_1": p["b1"],
             "Unknown_words": " ".join(map(str, p["words"]))} for p in cx.provinces]


def province_scenario_rows(cx: Context) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        pf = cx.rom.province_factions(sc)
        rulers = cx.rulers(sc)
        for r in cx.rom.scenario_provinces(sc):
            k = r["id"]
            rows.append({"劇本": sc + 1, "Id": k + 1, "名": cx.province(k), "勢力": rulers.get(pf.get(k, 0xFF), ""),
                         "人口": r["population"], "金": r["gold"], "米": r["food"], "開発": r["develop"],
                         "治水": r["flood"], "商業": r["commerce"], "税率": r["tax"], "民忠": r["loyalty"],
                         "訓練": r["training"], "士気": r["morale"], "Unknown_1": r["w1"], "Unknown_9_11": f"{r['b9']} {r['b10']} {r['b11']}",
                         "Unknown_13": r["b13"], "Unknown_19_23": f"{r['w19']} {r['w21']} {r['w23']}",
                         "Unknown_25_27": f"{r['b25']} {r['b26']} {r['b27']}"})
    return rows


def faction_rows(cx: Context) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        header = cx.rom.scenario_header(sc)["raw"]
        pf = cx.rom.province_factions(sc)
        rulers = cx.rulers(sc)
        for f in cx.rom.scenario_factions(sc):
            if f["ruler"] == NONE16:
                continue
            provs = [cx.province(k) for k, v in sorted(pf.items()) if v == f["id"]]
            rows.append({"劇本": sc + 1, "勢力": f["id"], "君主": rulers[f["id"]], "首都": cx.province(f["capital"]),
                         "州數": len(provs), "州": "、".join(provs), "旗色": header[4 + f["id"]] if f["id"] < 18 else "",
                         "Unknown_3": f["b3"], "Unknown_4_24": " ".join(map(str, f["rel"]))})
    return rows


def item_rows(cx: Context) -> list[dict]:
    rows = []
    for it in cx.items:
        row = {"Id": it["id"], "名": it["name"], "種類": ITEM_KINDS.get(it["kind"], it["kind"]),
               "能力加算(推測)": it["bonus"], "Unknown_1_2_4": f"{it['b1']} {it['b2']} {it['b4']}"}
        for sc, owner in enumerate(it["owners"]):
            row[f"劇本{sc + 1}_所有者"] = cx.person(owner) if owner < len(cx.persons) else ("" if owner == NONE16 else owner)
        rows.append(row)
    return rows


def scenario_rows(cx: Context) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        h = cx.rom.scenario_header(sc)
        rulers = cx.rulers(sc)
        rows.append({"劇本": sc + 1, "標題": cx.titles[sc], "年": h["year"], "勢力數": h["factions"],
                     "君主": "、".join(rulers[f] for f in sorted(rulers)),
                     "Header": h["raw"].hex(" "), "Extra": " ".join(f"{v:02X}" for v in cx.rom.scenario_extra(sc))})
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


def composite_parts(rom: Rom, path: str, scale: int = 3) -> None:
    """Every composite-face part: one row per type, the variants of parts 0-4 side by side (grey = not drawn)."""
    w = sum(PART_VARIANTS) * (FACE_W * 8 + 2) + 4 * 8
    im = Image.new("RGB", (w, COMPOSITE_TYPES * (FACE_H * 8 + 2)), (255, 255, 255))
    colours = [bgr555_rgb(c) for c in rom.face_palette()]
    for t in range(COMPOSITE_TYPES):
        x0 = 0
        for p, n in enumerate(PART_VARIANTS):
            for v in range(n):
                cell = Image.new("RGB", (FACE_W * 8, FACE_H * 8), (160, 160, 160))
                for c, raw in rom.composite_part(t, p, v):
                    for i, px in enumerate(decode_tile(raw)):
                        cell.putpixel((c % FACE_W * 8 + i % 8, c // FACE_W * 8 + i // 8), colours[px])
                im.paste(cell, (x0, t * (FACE_H * 8 + 2)))
                x0 += FACE_W * 8 + 2
            x0 += 8
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(path)


def map_images(rom: Rom, out: str) -> None:
    w, h = MAP_W * 8, MAP_H * 8
    png(w, h, rom.map_rgb(), os.path.join(out, "map.png"))
    for sc in range(SCENARIO_COUNT):
        png(w, h, rom.map_rgb(sc), os.path.join(out, f"map_scenario{sc + 1}.png"))
    scale = 4
    im = png(w, h, rom.map_rgb(), "", scale)
    dr = ImageDraw.Draw(im)
    f = font(14)
    for p, (x, y) in zip(rom.provinces(), rom.map_cells()):
        dr.text(((x + 1) * 8 * scale + 2, (y * 8 + 4) * scale), f"{p['id']} {p['name']}", fill="white", anchor="lm",
                font=f, stroke_width=2, stroke_fill="black")
    im.save(os.path.join(out, "map_provinces.png"))


def tactical_files(rom: Rom, out: str) -> None:
    """Per province: the three layers of its battlefield as CSV, and a schematic PNG of layer B (unrendered)."""
    os.makedirs(out, exist_ok=True)
    for p in rom.provinces():
        k = p["id"] - 1
        layers = rom.tactical_map(k)
        base = os.path.join(out, f"{p['id']:02d}_{p['name']}")
        with open(base + ".csv", "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f)
            for name, grid in zip("ABC", layers):
                wr.writerow([f"layer {name} (entry {TACTICAL_ENTRY + k})"])
                wr.writerows([[f"{v:02X}" for v in row] for row in grid])
        cell = 8
        grid = layers[1]
        im = Image.new("RGB", (TACTICAL_W * cell, len(grid) * cell))
        dr = ImageDraw.Draw(im)
        for y, row in enumerate(grid):
            for x, v in enumerate(row):
                colour = ((v * 67) % 200 + 40, (v * 131) % 200 + 40, (v * 29) % 200 + 40)
                dr.rectangle([x * cell, y * cell, x * cell + cell - 1, y * cell + cell - 1], fill=colour)
        im.save(base + "_B.png")
    print(f"戰場 {PROVINCE_COUNT} 州 → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 三國志III 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    cx = Context(rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(cx), "劇本人物": person_scenario_rows(cx), "州": province_rows(cx),
              "劇本州": province_scenario_rows(cx), "勢力": faction_rows(cx), "寶物": item_rows(cx),
              "劇本": scenario_rows(cx)}
    names = ("persons", "person_scenarios", "provinces", "province_scenarios", "factions", "items", "scenarios")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "san3.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p in cx.persons:
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["face"]), os.path.join(faces, f"{p['id']:03d}_{p['name']}.png"))
    for n in range(1, FACE_COUNT + 1):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"P{n:03d}.png"))
    composite_parts(rom, os.path.join(args.out, "composite_parts.png"))
    print(f"頭像 {len(cx.persons)} 人＋{FACE_COUNT} 張 → {args.out}")
    map_images(rom, args.out)
    print(f"大地圖 → {args.out}/map*.png")
    tactical_files(rom, os.path.join(args.out, "tactical"))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
