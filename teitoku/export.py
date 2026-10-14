#!/usr/bin/env python3
"""匯出 SFC 提督の決断 的劇本、艦船、基地、艦隊、提督、他國、頭像、艦船圖與地圖。

Usage: .venv/bin/python teitoku/export.py [--rom ROM] [--out DIR]

Writes scenarios.csv, ship_types.csv, ships.csv (270 ships, fixed fields), ship_scenarios.csv (9 x 270),
bases.csv (50 bases, fixed fields), base_scenarios.csv, fleets.csv, admirals.csv, admiral_scenarios.csv,
countries.csv, sides.csv (+ teitoku.xlsx when openpyxl is installed), faces/ (54 PNG), ships/ (one PNG per ship
class), scenes/ (entries 167-185), world_map.png (256 x 120), sea_map.png (1024 x 512), sea_map_bases.png
(bases marked) and font.png (the 1036 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    ADMIRAL_COUNT,
    ALLIANCE,
    DEFAULT_ROM,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    GLYPH_COUNT,
    OTHER_FACES,
    SCENARIO_COUNT,
    SCENE_COUNT,
    SCENE_FIRST_ENTRY,
    SCENE_H,
    SCENE_PALETTES,
    SCENE_W,
    SEA_BLOCK,
    SEA_H,
    SEA_W,
    SHIP_PIC_H,
    SHIP_PIC_W,
    SIDE_NAMES,
    WORLD_H,
    WORLD_W,
    Rom,
    bgr555_rgb,
    tiles_pixels,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
SCENARIOS = range(1, SCENARIO_COUNT + 1)


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def scenario_rows(rom: Rom) -> list[dict]:
    return [{"劇本": s["id"], "標題": s["title"], "日期": s["date"], "昭和": s["date_text"],
             "開始經過月數": rom.elapsed_months(s["id"])} for s in rom.scenarios()]


def type_rows(rom: Rom) -> list[dict]:
    return [{"艦種": t, "名稱": n} for t, n in enumerate(rom.type_names()) if n]


def ship_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in rom.ships(1):
        rows.append({"Id": s["id"], "艦名": s["name"], "讀音": s["reading"], "陣營": SIDE_NAMES[s["side"]],
                     "艦種": s["type"], "艦種名": s["type_name"], "艦級": s["class"], "艦船圖": rom.ship_picture_entry(s["class"]),
                     "対艦(推測)": s["anti_ship"], "対空(推測)": s["anti_air"], "装甲(推測)": s["armor"],
                     "速度": s["speed"], "搭載数(推測)": s["capacity"], "完成月(1941-11起)": s["complete_month"]})
    return rows


def ship_scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        for s in rom.ships(sc):
            rows.append({"劇本": sc, "Id": s["id"], "艦名": s["name"], "陣營": SIDE_NAMES[s["side"]], "所屬艦隊": s["fleet"],
                         "建造中": s["building"], "沈沒": s["sunk"], "戦闘機": s["fighters"], "攻撃機": s["attackers"],
                         "偵察機": s["scouts"], "兵員": s["troops"], "搭載数(推測)": s["capacity"],
                         "Unknown0E": s["unk_0e"], "Unknown0F": s["unk_0f"], "Unknown10": s["unk_10"],
                         "Unknown12": s["unk_12"], "狀態+14": f"{s['status']:02X}", "旗標+15": f"{s['flags']:02X}"})
    return rows


def base_rows(rom: Rom) -> list[dict]:
    return [{"Id": b["id"], "代號": b["code"], "基地名": b["name"], "X": b["x"], "Y": b["y"],
             "大地圖格": f"{b['x'] // SEA_BLOCK},{b['y'] // SEA_BLOCK}"} for b in rom.bases(1)]


def base_scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        hq = {s["hq"] for s in rom.sides(sc)}
        for b in rom.bases(sc):
            rows.append({"劇本": sc, "Id": b["id"], "代號": b["code"], "基地名": b["name"], "所屬": "日連"[b["owner"]],
                         "司令部": int(b["id"] in hq), "友好": b["friendship"], "耐久": b["durability"],
                         "耐久上限": b["durability_max"], "武装": b["armament"], "武装上限": b["armament_max"],
                         "鉄鉱": b["iron"], "原油": b["oil"], "人口": b["population"], "工業": b["industry"],
                         "戦闘機": b["fighters"], "攻撃機": b["attackers"], "偵察機": b["scouts"],
                         "双発機(推測)": b["twin_engine"], "ロケット弾": b["rockets"], "大型機(推測)": b["large_planes"],
                         "燃料": b["fuel"], "資材": b["materials"], "兵員": b["troops"], "兵員輸送船": b["troop_ships"],
                         "燃料輸送船": b["fuel_ships"], "Unknown22": b["unk_22"], "旗標+38": f"{b['flags']:04X}",
                         "原始資料": b["raw"]})
    return rows


def fleet_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        ships, bases, adm = rom.ships(sc), rom.bases(sc), rom.admirals(sc)
        for f in rom.fleets(sc):
            members = [s for s in ships if s["side"] == f["side"] and s["fleet"] == f["number"]]
            rows.append({"劇本": sc, "陣營": SIDE_NAMES[f["side"]], "艦隊": f["number"], "X": f["x"], "Y": f["y"],
                         "目的X": f["dest_x"], "目的Y": f["dest_y"],
                         "基地": bases[f["base"]]["name"] if f["base"] >= 0 else "",
                         "司令官": adm[f["admiral"]]["name"] if f["admiral"] >= 0 else "",
                         "旗艦": ships[f["flagship"]]["name"], "艦數": len(members),
                         "艦船": "、".join(s["name"] for s in members), "燃料": f["fuel"], "士気": f["morale"],
                         "疲労": f["fatigue"], "燃料輸送船": f["fuel_ships"],
                         "兵員輸送船": len(f["troop_ships"]), "輸送船兵員": sum(f["troop_ships"]), "原始資料": f["raw"]})
    return rows


def admiral_rows(rom: Rom) -> list[dict]:
    return [{"Id": a["id"], "姓名": a["name"], "陣營": SIDE_NAMES[a["side"]], "頭像": a["face"]} for a in rom.admirals(1)]


def admiral_scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        for a in rom.admirals(sc):
            rows.append({"劇本": sc, "Id": a["id"], "姓名": a["name"], "指揮艦隊": a["fleet"] or "",
                         "不登場(戦死等)": a["absent"], "旗標+22": f"{a['flags']:02X}"})
    return rows


def country_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        for c in rom.countries(sc):
            rows.append({"劇本": sc, "Id": c["id"], "國名": c["name"], "同盟": ALLIANCE[c["alliance"]],
                         "対日": c["to_japan"], "対連": c["to_allies"],
                         **{f"數值{k + 1}(未解)": v for k, v in enumerate(c["values"])},
                         "旗標(推測 bit0 レーダー bit1 新型戦闘機 bit3 長距離爆撃機)": f"{c['flags']:02X}"})
    return rows


def side_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        bases = rom.bases(sc)
        for s in rom.sides(sc):
            rows.append({"劇本": sc, "陣營": s["name"], "司令部": bases[s["hq"]]["name"], "原始資料": s["raw"]})
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


def images(rom: Rom, out: str) -> None:
    faces = os.path.join(out, "faces")
    os.makedirs(faces, exist_ok=True)
    names = {a["face"]: a["name"].replace(" ", "") for a in rom.admirals()[:ADMIRAL_COUNT]}
    for n in range(FACE_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(faces, f"{n:02d}_{names.get(n, OTHER_FACES.get(n))}.png"))
    ships = os.path.join(out, "ships")
    os.makedirs(ships, exist_ok=True)
    classes = {}
    for s in rom.ships(1):
        classes.setdefault(s["class"], s["name"])
    for c, name in sorted(classes.items()):
        png(SHIP_PIC_W * 8, SHIP_PIC_H * 8, rom.ship_picture_rgb(c), os.path.join(ships, f"{c:03d}_{name}.png"))
    scenes = os.path.join(out, "scenes")
    os.makedirs(scenes, exist_ok=True)
    for k in range(SCENE_COUNT):
        pal = [bgr555_rgb(v) for v in rom.palette(SCENE_PALETTES + 32 * k)]
        px = tiles_pixels(rom.entry(SCENE_FIRST_ENTRY + k), SCENE_W, SCENE_H)
        png(SCENE_W * 8, SCENE_H * 8, [pal[v] for v in px], os.path.join(scenes, f"{SCENE_FIRST_ENTRY + k}.png"))
    png(WORLD_W * 8, WORLD_H * 8, rom.world_rgb(), os.path.join(out, "world_map.png"))
    w, h = SEA_W * 32, SEA_H * 32
    png(w, h, rom.sea_rgb(), os.path.join(out, "sea_map.png"))
    big = Image.open(os.path.join(out, "sea_map.png")).resize((w * 2, h * 2), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    f = font(16)
    for b in rom.bases(1):  # map coordinates: 120 per 32-pixel block -> x 64 / 120 on the doubled image
        x, y = b["x"] * 64 // SEA_BLOCK, b["y"] * 64 // SEA_BLOCK
        dr.ellipse([x - 5, y - 5, x + 5, y + 5], outline="red", width=2)
        dr.text((x + 8, y), f"{b['code']} {b['name']}", fill="white", anchor="lm", font=f, stroke_width=2,
                stroke_fill="black")
    big.save(os.path.join(out, "sea_map_bases.png"))
    cols = 64
    im = Image.new("L", (cols * 17, (GLYPH_COUNT + cols - 1) // cols * 17), 255)
    px = im.load()
    for g in range(GLYPH_COUNT):
        for y, row in enumerate(rom.glyph(g)):
            for x, v in enumerate(row):
                if v:
                    px[g % cols * 17 + x, g // cols * 17 + y] = 0
    im.save(os.path.join(out, "font.png"))
    print(f"已匯出圖片 → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 提督の決断 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    sheets = {"劇本": scenario_rows(rom), "艦種": type_rows(rom), "艦船": ship_rows(rom), "劇本艦船": ship_scenario_rows(rom),
              "基地": base_rows(rom), "劇本基地": base_scenario_rows(rom), "艦隊": fleet_rows(rom), "提督": admiral_rows(rom),
              "劇本提督": admiral_scenario_rows(rom), "他國": country_rows(rom), "陣營": side_rows(rom)}
    names = ("scenarios", "ship_types", "ships", "ship_scenarios", "bases", "base_scenarios", "fleets", "admirals",
             "admiral_scenarios", "countries", "sides")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "teitoku.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")
    images(rom, args.out)


if __name__ == "__main__":
    main()
