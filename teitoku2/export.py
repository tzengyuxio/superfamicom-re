#!/usr/bin/env python3
"""匯出 SFC 提督の決断II 的劇本、艦型、艦船、艦隊、潜水艦、航空機、戦車、基地、拠点、國家、國力、予備兵力、提督、將軍、頭像與大地圖。

Usage: .venv/bin/python teitoku2/export.py [--rom ROM] [--out DIR]

CSV（UTF-8-BOM）：scenarios, ship_classes（共用 152）, sub_classes（共用 28）, ships, fleets, submarines, aircraft,
tanks, bases, kyoten, countries, sides, navy_reserve, army_reserve, marines, admirals, generals（除 ship_classes /
sub_classes / admirals / generals 外每列都有「劇本」欄，10 劇本）；teitoku2.xlsx（同內容，需 openpyxl）；
faces/（104 張 PNG）、world_map.png（640 × 360 海陸位圖）、world_map_marks.png（拠点與基地標記，2 倍）、font.png（1216 字）。
欄名標「(推測)」者未經遊戲畫面驗證，Unknown 欄位為原始值。
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    COUNTRY_NAMES,
    DEFAULT_ROM,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    FLEET_MISSIONS,
    GLYPH_COUNT,
    MAP_H,
    MAP_W,
    MARINE_COUNT,
    MARINE_SIZE,
    MARINES,
    OTHER_FACES,
    RESOURCE_LEVELS,
    SCENARIO_COUNT,
    SIDE_NAMES,
    TERRAIN,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
SCENARIOS = range(SCENARIO_COUNT)


def country(c: int) -> str:
    return COUNTRY_NAMES[c] if c < len(COUNTRY_NAMES) else f"?{c}"


def scenario_rows(rom: Rom) -> list[dict]:
    return [{"劇本": t["id"], "標題": t["title"], "開始日期": t["date"], "Unknown(日期表後)": t["unk"]}
            for t in rom.titles()]


def class_rows(rom: Rom) -> list[dict]:
    types = rom.type_names()
    return [{"Id": c["id"], "艦型": c["name"], "國": country(c["country"]), "艦種": types[c["type"]] if c["type"] < 8 else
             c["type"], "対艦": c["anti_ship"], "対空": c["anti_air"], "水雷": c["torpedo"], "速度": c["speed"],
             "搭載": c["aircraft"], "物資": c["supplies"], "装甲上": c["armor"][0], "装甲左": c["armor"][1],
             "装甲右": c["armor"][2], "装甲下": c["armor"][3], "艦船圖(推測)": c["picture"],
             "新型兵器(推測,110-149)": int(c["id"] >= 110)} for c in rom.ship_classes(rom.wram_image(0))]


def sub_class_rows(rom: Rom) -> list[dict]:
    return [{"Id": c["id"], "潜水艦型": c["name"], "國": country(c["country"]), "装甲": c["armor"], "速度": c["speed"],
             "水雷": c["torpedo"], "物資": c["supplies"], "圖(推測)": c["picture"]}
            for c in rom.sub_classes(rom.wram_image(0))]


def per_scenario(rom: Rom, fn) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        img = rom.wram_image(sc)
        rows += [{"劇本": sc, **r} for r in fn(img)]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 提督の決断II 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    types, air_types, abbr = rom.type_names(), rom.air_type_names(), rom.country_abbr()
    classes = rom.ship_classes(rom.wram_image(0))
    sub_classes = rom.sub_classes(rom.wram_image(0))

    def ships(img):
        return [{"Id": s["id"], "艦名": s["name"], "讀音": s["reading"],
                 "艦型": classes[s["class"]]["name"] if s["class"] >= 0 else "",
                 "艦種": types[classes[s["class"]]["type"]] if s["class"] >= 0 else "",
                 "國": country(classes[s["class"]]["country"]) if s["class"] >= 0 else "",
                 "対艦": s["anti_ship"], "対空": s["anti_air"], "装甲上": s["armor"][0], "装甲左": s["armor"][1],
                 "装甲右": s["armor"][2], "装甲下": s["armor"][3], "速度": s["speed"], "練度": s["skill"],
                 "Unknown15": s["unk_15"], "Unknown16": s["unk_16"], "Unknown18": s["unk_18"],
                 "Unknown20-27": s["unk_20"], "Unknown34": s["unk_34"], "Unknown35": s["unk_35"]}
                for s in rom.ships(img) if s["name"]]

    def fleets(img):
        adm, bases = rom.admirals(img), rom.bases(img)
        out = []
        for f in rom.fleets(img):
            if f["admiral"] < 0:
                continue
            port = bool(f["mission"] & 0x10)
            out.append({"Id": f["id"], "艦隊": f"第{f['id'] + 1}艦隊(推測編號)", "提督": adm[f["admiral"]]["name"],
                        "在港": int(port), "所在基地": bases[f["x"] & 0xFF]["name"] if port else "",
                        "X": "" if port else f["x"], "Y": "" if port else f["y"],
                        "任務": FLEET_MISSIONS.get(f["mission"], f"{f['mission']:02X}"),
                        "目標": bases[f["target_x"]]["code"] if f["mission"] == 0x04 else
                        (f"{f['target_x']}-{f['target_y']}" if f["mission"] == 0x07 else ""), "原始資料": f["raw"]})
        return out

    def submarines(img):
        return [{"Id": s["id"], "艦名": s["name"], "潜水艦型": sub_classes[s["class"]]["name"], "X": s["x"], "Y": s["y"],
                 "目標X": s["dest_x"], "目標Y": s["dest_y"], "水雷": s["torpedo"], "速度": s["speed"],
                 "物資": s["supplies"], "練度(推測)": s["skill"], "原始資料": s["raw"]}
                for s in rom.submarines(img) if s["class"] != 0xFF]

    def aircraft(img):
        return [{"Id": a["id"], "機名": a["name"], "國": country(a["country"]), "種別": air_types[a["type"]],
                 "戦闘": a["combat"], "航続": a["range"], "旗標(未解)": f"{a['flags']:02X}"}
                for a in rom.aircraft(img) if a["name"]]

    def tanks(img):
        return [{"Id": t["id"], "戦車": t["name"], "口径": t["caliber"], "装甲": t["armor"],
                 "旗標(推測 bit0 可用)": t["flags"]} for t in rom.tanks(img) if t["name"]]

    def bases(img):
        return [{"Id": b["id"], "代碼": b["code"], "基地名": b["name"], "擁有國": country(b["owner"]),
                 "原屬國(推測)": country(b["country"]), "X(推測)": b["x"], "Y(推測)": b["y"], "生産力": b["production"],
                 "生産力最大": b["production_max"], "油": RESOURCE_LEVELS[b["oil"]], "鉱": RESOURCE_LEVELS[b["ore"]],
                 "鄰接(推測)": " ".join(str(v) for v in b["links"]), "原始資料": b["raw"]} for b in rom.bases(img)]

    def kyoten(img):
        return [{"Id": k["id"], "No": k["id"] + 1, "拠点名": k["name"], "擁有國": abbr[k["owner"]], "X": k["x"],
                 "Y": k["y"], "地形": TERRAIN[k["terrain"]], "鄰接(推測)": " ".join(str(v) for v in k["links"])}
                for k in rom.kyoten(img)]

    def countries(img):
        return [{"Id": c["id"], "國名": c["country"], "簡稱": abbr[c["id"]], "領袖": c["leader"], "稱號": c["title"],
                 "對日友好度": c["japan_friendship"], "旗標(未解)": f"{c['flags']:02X}"} for c in rom.countries(img)]

    def sides(img):
        return [{"陣營": s["side"], "国民生産力": s["gnp"], "情報技術力": s["tech_intel"], "艦船技術力": s["tech_ships"],
                 "航空技術力": s["tech_aircraft"], "兵器技術力": s["tech_weapons"], "工業技術力": s["tech_industry"],
                 "基地維持費": s["base_upkeep"],
                 "軍事協定・同盟": " ".join(abbr[c] for c in s["alliance"]), "援助協定": " ".join(abbr[c] for c in s["aid"]),
                 "原始資料": s["raw"]} for s in rom.sides(img)]

    def navy(img):
        ac = rom.aircraft(img)
        return [{"陣營": SIDE_NAMES[r["side"]], "海軍費": r["budget"], "軍需物資": r["materials"], "陸戦隊": r["marines"],
                 "輸送船": r["transports"], **{f"{air_types[k // 2]}{'AB'[k % 2]}": f"{ac[a]['name']} {n}" if a != 0xFF
                                               else "" for k, (a, n) in enumerate(r["aircraft"])}}
                for r in rom.navy_reserve(img)]

    def army(img):
        ac = rom.aircraft(img)
        return [{"陣營": SIDE_NAMES[r["side"]], "陸軍費": r["budget"], "物資": r["materials"], "歩兵師団": r["infantry"],
                 "戦車師団": r["armored"], "トラック": r["trucks"],
                 **{f"{air_types[7 + k // 2]}{'AB'[k % 2]}": f"{ac[a]['name']} {n}" if a != 0xFF else ""
                    for k, (a, n) in enumerate(r["aircraft"])}} for r in rom.army_reserve(img)]

    def marines(img):
        gens, bs = rom.generals(img), rom.bases(img)
        out = []
        for k in range(MARINE_COUNT):
            b = img[MARINES + MARINE_SIZE * k:MARINES + MARINE_SIZE * (k + 1)]
            if b[1] == 0 and b[2] == 0:
                continue
            out.append({"No": k + 1, "兵力": b[1], "所在基地(推測)": bs[b[2]]["code"] if b[2] < len(bs) else b[2],
                        "任務(推測)": {2: "防衛", 4: "無し"}.get(b[3] & 0x0F, f"{b[3]:02X}"),
                        "目標基地": bs[b[4]]["code"] if b[4] != 0xFF else "",
                        "指揮官": gens[b[6]]["name"] if b[6] != 0xFF else "", "原始資料": bytes(b).hex()})
        return out

    img0 = rom.wram_image(0)
    admirals = [{"Id": a["id"], "姓名": a["name"], "陣營": SIDE_NAMES[a["side"]], "頭像": a["face"],
                 "Unknown14": a["unk_14"], "Unknown15": a["unk_15"], "Unknown16": a["unk_16"]} for a in rom.admirals(img0)]
    generals = [{"Id": g["id"], "姓名": g["name"], "陣營": SIDE_NAMES[g["side"]], "頭像": g["face"],
                 "Unknown14": g["unk_14"], "Unknown15": g["unk_15"], "Unknown16": g["unk_16"], "Unknown17": g["unk_17"]}
                for g in rom.generals(img0)]
    sheets = {
        "scenarios": ("劇本", scenario_rows(rom)), "ship_classes": ("艦型", class_rows(rom)),
        "sub_classes": ("潜水艦型", sub_class_rows(rom)), "ships": ("艦船", per_scenario(rom, ships)),
        "fleets": ("艦隊", per_scenario(rom, fleets)), "submarines": ("潜水艦", per_scenario(rom, submarines)),
        "aircraft": ("航空機", per_scenario(rom, aircraft)), "tanks": ("戦車", per_scenario(rom, tanks)),
        "bases": ("基地", per_scenario(rom, bases)), "kyoten": ("拠点", per_scenario(rom, kyoten)),
        "countries": ("國家", per_scenario(rom, countries)), "sides": ("國力", per_scenario(rom, sides)),
        "navy_reserve": ("海軍予備", per_scenario(rom, navy)), "army_reserve": ("陸軍予備", per_scenario(rom, army)),
        "marines": ("陸戦隊", per_scenario(rom, marines)), "admirals": ("提督", admirals),
        "generals": ("將軍", generals),
    }
    for fn, (_, rows) in sheets.items():
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx({title: rows for title, rows in sheets.values()}, os.path.join(args.out, "teitoku2.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")
    images(rom, args.out)


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
    img = rom.wram_image(0)
    names = {p["face"]: p["name"].replace(" ", "") for p in rom.admirals(img) + rom.generals(img)}
    for f in range(FACE_COUNT):
        im = Image.new("RGB", (FACE_W * 8, FACE_H * 8))
        im.putdata(rom.face_rgb(f))
        im.save(os.path.join(faces, f"{f:03d}_{names.get(f, OTHER_FACES.get(f))}.png"))
    bits = Image.new("RGB", (MAP_W, MAP_H))
    bits.putdata([(40, 70, 160) if rom.is_sea(x, y) else (120, 150, 80) for y in range(MAP_H) for x in range(MAP_W)])
    bits.save(os.path.join(out, "world_map.png"))
    big = bits.resize((MAP_W * 2, MAP_H * 2), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    f = font(11)
    for k in rom.kyoten(img):
        x, y = 2 * k["x"], 2 * k["y"]
        dr.rectangle([x - 2, y - 2, x + 2, y + 2], fill="yellow")
    for b in rom.bases(img):
        x, y = 2 * b["x"], 2 * b["y"]
        dr.ellipse([x - 4, y - 4, x + 4, y + 4], outline="red", width=2)
        dr.text((x + 6, y), b["code"], fill="white", anchor="lm", font=f, stroke_width=2, stroke_fill="black")
    big.save(os.path.join(out, "world_map_marks.png"))
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


if __name__ == "__main__":
    main()
