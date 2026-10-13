#!/usr/bin/env python3
"""匯出 SFC スーパー大航海時代 的人物、女性、港口、國家、艦隊、名稱表、頭像、世界地圖與港町圖。

Usage: .venv/bin/python daikoukai/export.py [--rom ROM] [--out DIR] [--no-map]

Writes persons.csv (player, 20 mates with abilities, 20 admirals = the new-game state), girls.csv, ports.csv,
nations.csv, fleets.csv, names.csv (+ daikoukai.xlsx when openpyxl is installed), faces/ (persons and girls),
portraits/ (F00-F52), mob_parts/ + mob_parts.png (composite face parts), map.png (16128 x 8064, palette
frame 0), map_small.png (1/4, ports marked), towns/ (every port's town picture with its new-game building
flags, and town_flags_XX.png for every flag combination the pieces react to).
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import parts_sheet
from rom import (
    CHUNK_TILES,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    MAP_H,
    MAP_W,
    METATILE_COUNT,
    NAME_LISTS,
    NATIONS,
    PORTRAIT_COUNT,
    STATS,
    TOWN_H,
    TOWN_W,
    Rom,
    decode_face_code,
    is_composite,
)


def png(rgb: list, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def face_label(code: int) -> str:
    if not is_composite(code):
        return f"F{code:02d}"
    head, pages = decode_face_code(code)
    return f"組合 頭{head} " + "".join(str(p) for p in pages)


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.persons():
        r = {"ID": p["id"], "姓名": p["name"], "身分": p["role"], "國(推定)": p["nation"], "戰鬥等級": p["battle"],
             "航海等級": p["sailing"]}
        if "age" in p:
            r.update({label: p[key] for key, label in STATS})
            r["能力表_byte6_9(未解)"] = p["stat_raw"].hex(" ")
        r.update({"頭像": face_label(p["face"]), "頭像碼": f"{p['face']:04X}", "旗標": f"{p['flags']:02X}",
                  "姓名指標(DATA)": f"{p['name_ptr']:04X}"})
        rows.append(r)
    return rows


def girl_rows(rom: Rom) -> list[dict]:
    return [{"ID": g["id"], "姓名": g["name"], "頭像(推定)": face_label(g["face"])} for g in rom.girls()]


def port_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.ports():
        r = {"ID": p["id"], "港名": p["name"], "種類": "補給港" if p["supply"] else "交易港",
             "chunk_x": p["chunk_x"], "chunk_y": p["chunk_y"], "metatile_x": p["mt_x"], "metatile_y": p["mt_y"],
             "像素_x": p["chunk_x"] * CHUNK_TILES * 8 + p["mt_x"] * 16,
             "像素_y": p["chunk_y"] * CHUNK_TILES * 8 + p["mt_y"] * 16,
             "地圖組(band)": rom.map_band(p["chunk_y"])}
        if not p["supply"]:
            r.update({"經濟圈": p["region"], "特產品": p["specialty"], "道具(推定)": p["item"],
                      "byte2(未解)": p["byte2"], "byte4(未解)": p["byte4"]})
        r["建物旗標"] = f"{p['flags']:02X}"
        rows.append(r)
    return rows


def nation_rows(rom: Rom) -> list[dict]:
    persons = rom.persons()
    rows = []
    for n, name in enumerate(NATIONS):
        adm = [p for p in persons if p["role"] == "提督" and p["flags"] >> 4 == n]
        mates = [p for p in persons if p["role"] == "航海士" and p["flags"] >> 4 == n]
        rows.append({"ID": n, "國名(推定)": name, "提督": "、".join(p["name"] for p in adm),
                     "提督ID": " ".join(str(p["id"]) for p in adm),
                     "航海士(旗標同國)": "、".join(p["name"] for p in mates)})
    return rows


def fleet_rows(rom: Rom) -> list[dict]:
    at = {(p["chunk_x"], p["chunk_y"], p["mt_x"], p["mt_y"]): p["name"] for p in rom.ports()}
    return [{"ID": f["id"], "chunk_x": f["loc"][0], "chunk_y": f["loc"][1], "metatile_x": f["loc"][2],
             "metatile_y": f["loc"][3], "所在港(座標與港口記錄相同)": at.get(f["loc"], ""),
             "byte4_15(未解)": f["raw"][4:].hex(" ")} for f in rom.fleets()]


def name_rows(rom: Rom) -> list[dict]:
    return [{"表": key, "編號": i, "名稱": n} for key in NAME_LISTS for i, n in enumerate(rom.name_list(key))]


def write_csv(rows: list[dict], path: str) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        fields = list(dict.fromkeys(k for r in rows for k in r))
        ws.append(fields)
        for r in rows:
            ws.append([r.get(k, "") for k in fields])
        ws.freeze_panes = "A2"
    wb.save(path)


def world_map(rom: Rom) -> Image.Image:
    """Whole world, pasted metatile by metatile (palette frame 0 of each latitude band)."""
    size = CHUNK_TILES * 8
    im = Image.new("RGB", (MAP_W * size, MAP_H * size))
    cache = {}
    for cy in range(MAP_H):
        band = rom.map_band(cy)
        for cx in range(MAP_W):
            for i, m in enumerate(rom.chunk_metatiles(cx, cy)):
                if (band, m) not in cache:
                    tile = Image.new("RGB", (16, 16))
                    tile.putdata(rom.metatile_pixels(band, m))
                    cache[band, m] = tile
                im.paste(cache[band, m], (cx * size + i % 14 * 16, cy * size + i // 14 * 16))
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC スーパー大航海時代 人物／港口／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="頭像與港町圖 PNG 放大倍率")
    ap.add_argument("--no-map", action="store_true", help="不輸出世界地圖（較快）")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "女性": girl_rows(rom), "港口": port_rows(rom), "國家": nation_rows(rom),
              "艦隊": fleet_rows(rom), "名稱": name_rows(rom)}
    for rows, name in zip(sheets.values(), ["persons", "girls", "ports", "nations", "fleets", "names"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "daikoukai.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    import export_kaodata
    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    chars = export_kaodata.characters(rom)
    w, h = FACE_W * 8, FACE_H * 8
    for c in chars:
        png(rom.face_rgb(c["face_code"]), w, h, os.path.join(faces, f"{c['id']:02d}_{c['name']}.png"), args.scale)
    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for n in range(PORTRAIT_COUNT):
        png(rom.face_rgb(n), w, h, os.path.join(portraits, f"F{n:02d}.png"), args.scale)
    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)

    towns = os.path.join(args.out, "towns")
    os.makedirs(towns, exist_ok=True)
    ports = rom.ports()
    for p in ports:
        png(rom.town_rgb(p["id"]), TOWN_W * 8, TOWN_H * 8, os.path.join(towns, f"{p['id']:02d}_{p['name']}.png"),
            args.scale)
    for flags in (0x00, 0x04, 0x10, 0x14):     # the two flag bits the pieces react to (trading ports)
        png(rom.town_rgb(0, flags), TOWN_W * 8, TOWN_H * 8, os.path.join(towns, f"town_flags_{flags:02X}.png"),
            args.scale)

    print(f"已匯出人物 {len(sheets['人物'])} 筆、女性 {len(sheets['女性'])} 筆、港口 {len(ports)} 筆、"
          f"國家 {len(sheets['國家'])} 筆、艦隊 {len(sheets['艦隊'])} 筆、名稱 {len(sheets['名稱'])} 筆 → {args.out}")
    print(f"頭像 {len(chars)} 人＋專屬 {PORTRAIT_COUNT} 張；港町圖 {len(ports)} 港＋4 種旗標組合")

    if not args.no_map:
        im = world_map(rom)
        im.save(os.path.join(args.out, "map.png"))
        small = im.reduce(4)
        d = ImageDraw.Draw(small)
        for r in sheets["港口"]:
            x, y = (r["像素_x"] + 8) // 4, (r["像素_y"] + 8) // 4
            d.rectangle((x - 3, y - 3, x + 3, y + 3), fill=(255, 0, 0) if r["種類"] == "交易港" else (255, 255, 0),
                        outline=(0, 0, 0))
            d.text((x + 5, y - 6), str(r["ID"]), fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        small.save(os.path.join(args.out, "map_small.png"))
        print(f"世界地圖 {im.width}×{im.height}（{METATILE_COUNT} 種 metatile × 4 緯度組；map_small.png 1/4，"
              f"紅＝交易港、黃＝補給港）")


if __name__ == "__main__":
    main()
