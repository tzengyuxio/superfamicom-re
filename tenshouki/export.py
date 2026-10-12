#!/usr/bin/env python3
"""匯出 SFC 信長の野望・天翔記 的人物、劇本人物、城、軍団、頭像與大地圖。

Usage: .venv/bin/python tenshouki/export.py [--rom ROM] [--out DIR] [--scale N]

Writes persons.csv, person_scenarios.csv (2 scenarios), castles.csv (2 x 128), corps.csv
(+ tenshouki.xlsx when openpyxl is installed), faces/ (one PNG per person), portraits/ (P000-P311),
face_packs.png (the 19 packs of 4 generic faces), mob_parts.png and mob_parts/, map.png
(terrain + roads), map_terrain.png and map_castles.png (castle numbers and names).
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from rom import (
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_H,
    FACE_W,
    MAP_H,
    MAP_W,
    PACK_COUNT,
    PACK_ENTRY,
    PERSON_COUNT,
    PORTRAIT_COUNT,
    RANKS,
    SCENARIO_COUNT,
    SCENARIO_YEARS,
    STATUS,
    TROOPS,
    UNITS,
    Rom,
    bgr555_rgb,
    decode_tile,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import parts_sheet


def png(w: int, h: int, rgb: list[tuple[int, int, int]], path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def face_label(code: int) -> str:
    if not code & 0x8000:
        return f"P{code:03d}"
    return f"組合 {code & 0x1F}-" + "".join(str(code >> s & 3) for s in (5, 7, 9, 11))


def person_rows(rom: Rom) -> list[dict]:
    by_face = {p["face"]: p["id"] for p in rom.persons()}
    rows = []
    for p in rom.persons():
        name1, name2 = "".join(rom.name(p["id"], 0)), "".join(rom.name(p["id"], 1))
        father = by_face.get(p["father_face"])
        rows.append({
            "Id": p["id"], "ROM_Offset": f"0x{p['offset']:05X}", "姓名": name1, "姓名(劇本2)": name2 if name2 != name1 else "",
            "生年": p["born"], "政治上限": p["politics_max"], "戦闘上限": p["war_max"], "智謀上限": p["intellect_max"],
            "魅力": p["charm"], "野望": p["ambition"],
            "父": "".join(rom.name(father, 0)) if father is not None else "",
            "Face": f"{p['face']:04X}", "頭像": face_label(p["face"]),
            "Unknown": p["unknown"], "Flags": f"{p['flags']:04X}",
        })
    return rows


def scenario_rows(rom: Rom) -> list[dict]:
    persons = rom.persons()
    rows = []
    for sc in range(SCENARIO_COUNT):
        castles = rom.castles(sc)
        lords = lord_names(rom, sc)
        for r in rom.scenario_persons(sc):
            p = persons[r["id"]]
            if not r["castle"]:
                continue  # not yet in play
            rows.append({
                "劇本": sc + 1, "年": SCENARIO_YEARS[sc], "記錄": r["slot"] + 1, "Id": r["id"],
                "姓名": "".join(rom.name(r["id"], sc)), "狀態": STATUS[r["status"]], "身分": RANKS[r["rank"]] if r["status"] < 3 else "",
                "大名": lords.get(r["daimyo"], ""), "軍団": r["corps"] if r["status"] < 3 else "", "城": castles[r["castle"] - 1]["name"],
                "年齢": SCENARIO_YEARS[sc] - p["born"] + 1,
                "政治": r["politics"] * p["politics_max"] // 200, "戦闘": r["war"] * p["war_max"] // 200,
                "智謀": r["intellect"] * p["intellect_max"] // 200,
                "忠誠": r["loyalty"] if r["status"] else "", "勲功": r["merit"] if r["merit"] != 999 else "",
                "兵士": r["soldiers"], "訓練": r["training"], "士気": r["morale"],
                "部隊": TROOPS[r["unit"]] if r["unit"] < len(TROOPS) else r["unit"],
                **{f"{u}適性": a for u, a in zip(UNITS, r["aptitude"])},
            })
    return rows


def lord_names(rom: Rom, sc: int) -> dict[int, str]:
    """大名 number -> 当主's name (the person of that daimyo with 身分 大名)."""
    return {r["daimyo"]: "".join(rom.name(r["id"], sc)) for r in rom.scenario_persons(sc) if r["castle"] and r["status"] == 0}


def castle_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        lords = lord_names(rom, sc)
        corps = {c["id"]: c for c in rom.corps(sc)}
        for c, (prov, x, y) in zip(rom.castles(sc), rom.castle_positions()):
            owner = corps.get(c["corps"])
            rows.append({"劇本": sc + 1, "城": c["id"], "名": c["name"], "国": prov, "x": x, "y": y,
                         "軍団": owner["id"] if owner else "",
                         "大名": lords.get(owner["daimyo"], "") if owner else "",
                         "城郭": c["walls"], "石高": c["koku"], "商業": c["commerce"], "人口": c["population"],
                         "民忠": c["loyalty"], "徴兵": c["draft"]})
    return rows


def corps_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        lords, castles = lord_names(rom, sc), rom.castles(sc)
        for c in rom.corps(sc):
            rows.append({"劇本": sc + 1, "軍団": c["id"], "大名": lords.get(c["daimyo"], ""),
                         "軍団長": "".join(rom.name(c["leader"], sc)), "居城": castles[c["castle"] - 1]["name"],
                         "金": c["gold"], "米": c["rice"]})
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


def face_packs(rom: Rom, path: str) -> None:
    """The 19 packs of 4 generic faces (palette of the pack), one row per pack."""
    w, h = FACE_W * 8, FACE_H * 8
    sheet = Image.new("RGB", (4 * (w + 4), PACK_COUNT * (h + 4)), "white")
    for pack in range(PACK_COUNT):
        e = rom.entry(PACK_ENTRY + pack)
        pal = [bgr555_rgb(c) for c in rom.face_palettes()[rom.face_palette_number(0x8000 | pack)]]
        for s in range(4):
            im = Image.new("RGB", (w, h))
            px = [0] * (w * h)
            for t in range(FACE_W * FACE_H):
                o = FACE_BYTES * s + 32 * t
                for i, v in enumerate(decode_tile(e[o:o + 32])):
                    px[(t // FACE_W * 8 + i // 8) * w + t % FACE_W * 8 + i % 8] = v
            im.putdata([pal[v] for v in px])
            sheet.paste(im, (s * (w + 4), pack * (h + 4)))
    sheet.save(path)


def castle_map(rom: Rom, path: str, scale: int) -> None:
    """map.png with every castle's number and name (scenario 1) at its map position."""
    w, h = MAP_W * 8, MAP_H * 8
    im = Image.new("RGB", (w, h))
    im.putdata(rom.map_pixels())
    im = im.resize((w * scale, h * scale), Image.NEAREST)
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(LABEL_FONT, 6 * scale)
    except OSError:
        font = ImageFont.load_default(6 * scale)
    for c, (_, x, y) in zip(rom.castles(0), rom.castle_positions()):
        cx, cy = (x * 8 + 4) * scale, (y * 8 + 4) * scale
        dr.rectangle([cx - 3, cy - 3, cx + 3, cy + 3], fill="red")
        dr.text((cx + 5, cy), f"{c['id']} {c['name']}", fill="white", anchor="lm", font=font,
                stroke_width=2, stroke_fill="black")
    im.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 信長の野望・天翔記 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2, help="地圖 PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "劇本人物": scenario_rows(rom), "城": castle_rows(rom), "軍団": corps_rows(rom)}
    for rows, fn in zip(sheets.values(), ("persons", "person_scenarios", "castles", "corps")):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "tenshouki.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p in rom.persons():
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["face"]), os.path.join(faces, f"{p['id']:03d}_{p['name']}.png"))
    for code in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(code), os.path.join(portraits, f"P{code:03d}.png"))
    face_packs(rom, os.path.join(args.out, "face_packs.png"))
    for name, roads in (("map", True), ("map_terrain", False)):
        im = Image.new("RGB", (MAP_W * 8, MAP_H * 8))
        im.putdata(rom.map_pixels(roads))
        im.resize((im.width * args.scale, im.height * args.scale), Image.NEAREST).save(os.path.join(args.out, f"{name}.png"))
    castle_map(rom, os.path.join(args.out, "map_castles.png"), args.scale)

    import export_kaodata
    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)
    print(f"頭像 {PERSON_COUNT} 人＋專屬 {PORTRAIT_COUNT} 張＋組合臉 {PACK_COUNT} 包 → {args.out}")


if __name__ == "__main__":
    main()
