#!/usr/bin/env python3
"""匯出 SFC 大航海時代II 的人物、VIP、女性、艦隊、船種、港、商品、道具、發見物、字串表、頭像、世界地圖與字型。

Usage: .venv/bin/python daikoukai2/export.py [--rom ROM] [--out DIR]

Writes persons.csv, heroes.csv, vips.csv, women.csv, fleets.csv, fleet_ships.csv, ship_types.csv, ports.csv,
goods.csv, items.csv, discoveries.csv, strings.csv (+ daikoukai2.xlsx when openpyxl is installed), faces/ (one PNG
per person), portraits/ (000-127), packs/ (the 7 composed-face packs), world_map.png (one pixel per 8 x 8 cell),
world_map_ports.png (labelled), world_map_mediterranean.png (full resolution) and font.png (the 1631 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BUILDINGS,
    CANNONS,
    COUNTRIES,
    DEFAULT_ROM,
    DISCOVERY_CATEGORIES,
    FACE_BYTES,
    FACE_H,
    FACE_W,
    FIGUREHEADS,
    FONT,
    GOODS,
    GOODS_CATEGORIES,
    HEROES,
    ITEM_CATEGORIES,
    LIQUORS,
    MAP_H,
    MAP_W,
    NAME_POOL,
    PACK_COUNT,
    PEERAGES,
    PORTRAIT_COUNT,
    RANKS,
    SKILLS,
    STAT_NAMES,
    STATS,
    WOODS,
    Rom,
    bgr555_rgb,
    decode_tile,
    le16,
    wram,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
STRING_TABLES = {"國家": COUNTRIES, "商品分類": GOODS_CATEGORIES, "大砲": CANNONS, "職位": RANKS, "技能": SKILLS,
                 "能力名": STAT_NAMES, "船材": WOODS, "船首像": FIGUREHEADS, "發見物分類": DISCOVERY_CATEGORIES,
                 "道具分類": ITEM_CATEGORIES, "酒": LIQUORS, "爵位": PEERAGES, "建物": BUILDINGS, "人名池": NAME_POOL}


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def hexs(raw: bytes) -> str:
    return raw.hex(" ")


def person_rows(rom: Rom) -> list[dict]:
    countries, ports = rom.string_table(COUNTRIES), rom.ports()
    rows = []
    for p in rom.persons():
        code = p["face"]
        rows.append({
            "Id": p["id"], "WRAM": f"7E{wram(0x87E09) + 50 * p['id']:04X}", "姓名": p["name"],
            "類別": "主角" if p["id"] < HEROES else "仲間" if p["id"] < 69 else "劇情人物" if p["id"] < 79 else "提督",
            **dict(zip(STATS, p["stats"])), "年齡": p["age"], "航海Lv": p["sail_level"], "航海經驗": p["sail_exp"],
            "戰鬥Lv": p["battle_level"], "戰鬥經驗": p["battle_exp"],
            "國籍": countries[p["country"]] if p["country"] < len(countries) else p["country"],
            "頭像碼": f"{code:04X}", "頭像": f"組合 包{rom.pack_of(code)}" if code & 0x8000 else f"專屬 {code:03d}",
            "母港(推測)": "" if p["port"] == 0xFF else ports[p["port"]]["name"] if p["port"] < len(ports) else p["port"],
            "+35(未解)": p["unk35"], "+43(未解)": p["unk43"], "+44(未解)": p["unk44"], "+46(未解)": p["unk46"],
            "+47(未解)": f"{p['unk47']:04X}", "+49高位(未解)": p["flags49"]})
    return rows


def hero_rows(rom: Rom) -> list[dict]:
    persons, fleets, countries = rom.persons(), rom.fleets(), rom.string_table(COUNTRIES)
    rows = []
    for p in persons[:HEROES]:
        f = fleets[1 + 10 * p["country"]]
        rows.append({"Id": p["id"], "姓名": p["name"], "年齡": p["age"], "國籍": countries[p["country"]],
                     **dict(zip(STATS, p["stats"])), "開始艦隊": f["id"], "艦隊船數": len(f["ships"])})
    return rows


def vip_rows(rom: Rom) -> list[dict]:
    ports = rom.ports()
    return [{"Id": v["id"], "名前": v["name"], "頭像": v["face"], "+17(未解)": v["kind"], "+20(未解)": v["unk20"],
             "+21 港(推測)": ports[v["port"]]["name"] if v["kind"] != 0xFF else "", "+21": v["port"]}
            for v in rom.vips()]


def women_rows(rom: Rom) -> list[dict]:
    ports = rom.ports()
    return [{"Id": w["id"], "名前": w["name"], "+13 年齡(推測)": w["age"],
             "+14 港(推測)": ports[w["port"]]["name"], "+14": w["port"], "+18(未解)": f"{w['unk18']:02X}"}
            for w in rom.women()]


def fleet_rows(rom: Rom) -> tuple[list[dict], list[dict]]:
    persons, ports, types = rom.persons(), rom.ports(), rom.ship_types()
    rows, ships = [], []
    for f in rom.fleets():
        adm = persons[f["admiral"]]["name"] if f["admiral"] < len(persons) else ""
        rows.append({"Id": f["id"], "WRAM": f"7E{wram(0x89965) + 133 * f['id']:04X}",
                     "提督": adm, "提督Id": f["admiral"], "母港": ports[f["port"]]["name"] if f["port"] < len(ports) else f["port"], "群內序": f["index"],
                     "啟用": f["active"], "船數": len(f["ships"]), "x": f["x"], "y": f["y"], "x2(未解)": f["x2"],
                     "y2(未解)": f["y2"], "+2(未解)": f["unk2"], "+111(未解)": f"{f['w111']:04X}",
                     "+115(未解)": " ".join(f"{v:04X}" for v in f["w115"])})
        for i, s in enumerate(f["ships"]):
            t = s[7] - 0x28
            ships.append({"艦隊": f["id"], "序": i, "船種(推測 +7-0x28)": types[t]["name"] if 0 <= t < len(types) else "",
                          "+0 LE16(推測 水夫)": le16(s, 0), "+2": s[2], "+3": s[3], "+4": s[4], "+5": s[5],
                          "+6": s[6], "+7": s[7], "+8": s[8], "hex": hexs(s)})
    return rows, ships


def ship_rows(rom: Rom) -> list[dict]:
    return [{"Id": t["id"], "船種": t["name"], "+18 編號": t["number"], "+19(未解)": f"{t['flags']:02X}",
             "+20(未解)": t["b20"], "+21 LE16(未解)": t["w21"], "+23 LE16(未解)": t["w23"],
             **{f"規格{i}": t["spec"][i] for i in range(6)}, "規格6 LE16": le16(t["spec"], 6), "規格8": t["spec"][8],
             "規格9": t["spec"][9], "規格10 LE16(推測 價格)": le16(t["spec"], 10)} for t in rom.ship_types()]


def port_rows(rom: Rom) -> list[dict]:
    countries, items = rom.string_table(COUNTRIES), rom.items()
    rows = []
    for p in rom.ports():
        r = {"Id": p["id"], "港名": p["name"], "x": p["x"], "y": p["y"], "種類": "交易港" if "state" in p else "補給港",
             "國籍": countries[p["country"]] if p["country"] < 6 else "", "旗標高位(未解)": p["flags"]}
        if "state" in p:
            r.update({"經濟(推測)": p["economy"], "工業(推測)": p["industry"],
                      **{f"占有率_{countries[i]}(推測)": v for i, v in enumerate(p["shares"])},
                      "商品分類價格(未解)": " ".join(map(str, p["price_levels"])), "地域(推測)": p["region"],
                      "+34(未解)": p["b34"], "+35(未解)": p["b35"],
                      "道具(推測)": "、".join(items[i]["name"] for i in p["items"] if i < len(items)),
                      "+0(未解)": p["unk0"], "+25(未解)": p["w25"], "+27(未解)": p["b27"], "+28(未解)": p["b28"]})
        rows.append(r)
    return rows


def item_rows(rom: Rom) -> list[dict]:
    cats = rom.string_table(ITEM_CATEGORIES)
    return [{"Id": i["id"], "名稱": i["name"], "分類": cats[i["category"]] if i["category"] < len(cats) else i["category"],
             "價格(推測)": i["price"], "效果值(推測)": i["power"], "+18(未解)": i["icon"], "說明": i["text"]}
            for i in rom.items()]


def string_rows(rom: Rom) -> list[dict]:
    rows = []
    for table, at in STRING_TABLES.items():
        rows += [{"表": table, "ROM": f"0x{at:05X}", "序": k, "字串": s} for k, s in enumerate(rom.string_table(at))]
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(f"已匯出 {len(rows)} 筆 → {path}")


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        keys = list(dict.fromkeys(k for r in rows for k in r))
        ws = wb.create_sheet(title)
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
    chars, pals = rom.map_chars(), rom.map_palettes()
    tiles = [decode_tile(chars[32 * t:32 * t + 32]) for t in range(256)]

    def tile_rgb(word: int) -> list[tuple[int, int, int]]:
        pal = pals[(word >> 10 & 7) - 2]
        return [bgr555_rgb(le16(pal, 2 * v)) for v in tiles[word & 0xFF]]

    cache: dict[int, list] = {}
    avg: dict[int, tuple] = {}
    small = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            w = rom.map_tile(x, y)
            if w not in avg:
                cache[w] = tile_rgb(w)
                avg[w] = tuple(sum(c[i] for c in cache[w]) // 64 for i in range(3))
            small.append(avg[w])
    im = Image.new("RGB", (MAP_W, MAP_H))
    im.putdata(small)
    im.save(os.path.join(out, "world_map.png"))
    big = im.resize((MAP_W * 2, MAP_H * 2), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    f = font(14)
    for p in rom.ports():
        x, y = p["x"] * 2, p["y"] * 2
        dr.rectangle([x - 3, y - 3, x + 3, y + 3], outline="red" if p["id"] < 100 else "yellow", width=2)
        dr.text((x + 6, y), f"{p['id']} {p['name']}", fill="white", anchor="lm", font=f, stroke_width=2,
                stroke_fill="black")
    big.save(os.path.join(out, "world_map_ports.png"))
    # full resolution: Atlantic coast of Europe, Mediterranean and North Sea (cells x 40-480, y 150-450)
    x0, y0, w, h = 40, 150, 440, 300
    im = Image.new("RGB", (w * 8, h * 8))
    for cy in range(h):
        for cx in range(w):
            word = rom.map_tile(x0 + cx, y0 + cy)
            if word not in cache:
                cache[word] = tile_rgb(word)
            tile_im = Image.new("RGB", (8, 8))
            tile_im.putdata(cache[word])
            im.paste(tile_im, (cx * 8, cy * 8))
    im.save(os.path.join(out, "world_map_mediterranean.png"))


def font_sheet(rom: Rom, path: str) -> None:
    n, cols = len(rom.charset), 32
    rows = (n + cols - 1) // cols
    im = Image.new("L", (cols * 17, rows * 17), 255)
    px = im.load()
    for g in range(n):
        raw = rom.data[FONT + 32 * g:FONT + 32 * g + 32]
        gx, gy = g % cols * 17, g // cols * 17
        for y in range(16):
            for x in range(16):
                if raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1:
                    px[gx + x, gy + y] = 0
    im.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 大航海時代II 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    fleets, fleet_ships = fleet_rows(rom)
    sheets = {"人物": person_rows(rom), "主角": hero_rows(rom), "VIP": vip_rows(rom), "女性": women_rows(rom),
              "艦隊": fleets, "艦隊船": fleet_ships, "船種": ship_rows(rom), "港": port_rows(rom),
              "商品": [{"Id": k, "商品": g} for k, g in enumerate(rom.string_table(GOODS))], "道具": item_rows(rom),
              "發見物": [{"Id": d["id"], "名稱": d["name"], "說明": d["text"]} for d in rom.discoveries()],
              "字串表": string_rows(rom)}
    names = ("persons", "heroes", "vips", "women", "fleets", "fleet_ships", "ship_types", "ports", "goods", "items",
             "discoveries", "strings")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "daikoukai2.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    for sub in ("faces", "portraits", "packs"):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)
    w, h = FACE_W * 8, FACE_H * 8
    for p in rom.persons():
        png(w, h, rom.face_rgb(p["face"]), os.path.join(args.out, "faces", f"{p['id']:03d}_{p['name']}.png"))
    for n in range(PORTRAIT_COUNT):
        png(w, h, rom.face_rgb(n), os.path.join(args.out, "portraits", f"{n:03d}.png"))
    for t in range(PACK_COUNT):  # the 8 whole faces of each pack side by side
        pack, pal = rom.pack_tiles(t), rom.face_palette(0x8000 | t << 12)
        colors = [bgr555_rgb(le16(pal, 2 * i)) for i in range(16)]
        sheet = Image.new("RGB", (8 * w, h))
        for k in range(8):
            px = [(0, 0, 0)] * (w * h)
            for c in range(30):
                for i, v in enumerate(decode_tile(pack[FACE_BYTES * k + 32 * c:FACE_BYTES * k + 32 * c + 32])):
                    px[(c // FACE_W * 8 + i // 8) * w + c % FACE_W * 8 + i % 8] = colors[v]
            face = Image.new("RGB", (w, h))
            face.putdata(px)
            sheet.paste(face, (k * w, 0))
        sheet.save(os.path.join(args.out, "packs", f"pack{t}.png"))
    map_images(rom, args.out)
    font_sheet(rom, os.path.join(args.out, "font.png"))
    print(f"頭像 {len(rom.persons())} 人＋{PORTRAIT_COUNT} 張＋組合臉 {PACK_COUNT} 包、世界地圖、字型 → {args.out}")


if __name__ == "__main__":
    main()
