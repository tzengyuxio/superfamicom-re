#!/usr/bin/env python3
"""匯出 SFC 太閤立志伝 的人物、名表、勢力、城、字串表、頭像、大地圖、戰場地圖與字型。

Usage: .venv/bin/python taikou/export.py [--rom ROM] [--out DIR]

Writes names.csv (716), persons.csv (713 records), factions.csv (20), castles.csv (125), strings.csv,
battle_fields.csv (19) (+ taikou.xlsx when openpyxl is installed), faces/ (one PNG per person record),
portraits/ (000-257), map.png (the Japan map, 5248 x 2944), map_castles.png (half size, castles labelled),
battle/ (the 19 battle fields, 496 x 224) and font.png (the 2048 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BATTLE_COUNT,
    BATTLE_FIRST,
    BLOCK,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    GLYPH_COUNT,
    PORTRAIT_COUNT,
    SKILL_GRADES,
    STATS,
    STRING_TABLES,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
# Which field the game picks ($C9:238E, read from the code, see docs/ROM_FORMAT.md §9); only field 6 is checked
# in the game (桶狭間)
FIELD_USE = {**{f: "城（推測：城狀態 +14 選 0–5）" for f in range(6)}, 6: "桶狭間（事件 $C9:14F3 固定）",
             **{f: "野戰（推測：依地圖格 byte 與亂數選 7–18）" for f in range(7, 19)}}


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([c or (0, 0, 0) for c in rgb])
    im.save(path)


def full_name(p: dict) -> str:
    return p["surname"] + p["given"]


def faction_names(rom: Rom, persons: list[dict]) -> dict[int, str]:
    """faction id -> its daimyo's name ("" when the faction has none)."""
    return {f["id"]: full_name(persons[f["daimyo"]]) if f["daimyo"] != 0xFF else "" for f in rom.factions()}


def name_rows(rom: Rom) -> list[dict]:
    return [{"Id": n["id"], "姓": n["surname"], "名": n["given"], "頭像碼": f"{n['face']:04X}",
             "頭像": f"組合 型{n['face'] >> 8 & 15}" if n["face"] & 0x8000 else f"專屬 {n['face']:03d}"}
            for n in rom.names()]


def person_rows(rom: Rom, persons: list[dict]) -> list[dict]:
    castles, ranks = rom.castles(), rom.string_table("ranks")
    skills = rom.string_table("skills")
    fname = faction_names(rom, persons)
    rows = []
    for p in persons:
        f, c = p["faction"], p["castle"]
        row = {"記錄": p["record"], "Id": p["id"], "姓名": full_name(p), "開始時": "登場" if p["start"] else "後登場",
               "所属(大名)": "浪人" if f == 0xFF else fname.get(f, "") or f"勢力{f}（無大名）",
               "勢力Id": "" if f == 0xFF else f, "身分": ranks[p["rank"]] if p["rank"] < len(ranks) else p["rank"],
               "居城(推測)": castles[c]["name"] if c < len(castles) else "", "居城Id(推測)": c,
               "政略Lv": p["政略Lv"], "戦術Lv": p["戦術Lv"], **{s: p[s] for s in STATS},
               **{sk: SKILL_GRADES[v] for sk, v in zip(skills, p["skills"])}, "頭像碼": f"{p['face']:04X}"}
        for i, (loc, cell) in enumerate(p["positions"]):
            row[f"位置{i + 1}(未解)"] = f"{loc}/{cell}"
        row.update({"Unknown26(推測兵數)": p["w26"], "Unknown28": p["b28"], "Unknown29": p["b29"],
                    "Unknown31": p["b31"], "Unknown32": p["b32"], "Unknown42_53": p["tail"].hex(" ")})
        rows.append(row)
    return rows


def faction_rows(rom: Rom, persons: list[dict]) -> list[dict]:
    castles = rom.castles()
    fname = faction_names(rom, persons)
    rows = []
    for f in rom.factions():
        rows.append({"Id": f["id"], "大名": fname[f["id"]], "大名記錄": "" if f["daimyo"] == 0xFF else f["daimyo"],
                     "本城(推測)": castles[f["castle"]]["name"] if f["castle"] < len(castles) else "",
                     "本城Id(推測)": f["castle"],
                     "城數": sum(1 for c in castles if c["state"] is not None and c["faction"] == f["id"]),
                     "Unknown1_20(對各勢力)": " ".join(f"{b:02X}" for b in f["relations"]),
                     "Unknown22": f["w22"], "Unknown24_32": f["tail"].hex(" ")})
    return rows


def castle_rows(rom: Rom, persons: list[dict]) -> list[dict]:
    castles = rom.castles()
    fname = faction_names(rom, persons)
    rows = []
    for c in castles:
        bx, by = c["block"]
        row = {"Id": c["id"], "名": c["name"], "相鄰": "、".join(castles[n]["name"] for n in c["neighbours"]),
               "地圖x(格)": bx * BLOCK + c["cell"] % BLOCK, "地圖y(格)": by * BLOCK + c["cell"] // BLOCK,
               "區塊位置": c["location"], "格": c["cell"], "Unknown16": c["b16"]}
        s = c["state"]
        if s is None:
            row.update({"勢力": "（開始時無）"})
        else:
            f = c["faction"]
            lord = c["lord"]
            row.update({"勢力": "" if f == 0xFF else fname.get(f, "") or f"勢力{f}",
                        "城主(推測)": full_name(persons[lord]) if lord < len(persons) else "",
                        "城主記錄(推測)": lord, "城圖示(+14 低 2 位)": c["s14"] & 3,
                        "狀態+0(城Id)": s[0], "狀態+3": c["s3"], "狀態+4": c["s4"], "狀態+5": c["s5"], "狀態+7": c["s7"],
                        "狀態+9": c["s9"], "狀態+10": c["s10"], "狀態+11": c["s11"], "狀態+13": c["s13"],
                        "狀態+14": f"{c['s14']:02X}", "狀態+15": c["s15"]})
        rows.append(row)
    keys = list(max(rows, key=len))
    return [{k: r.get(k, "") for k in keys} for r in rows]


def string_rows(rom: Rom) -> list[dict]:
    return [{"表": name, "ROM_Offset": f"0x{STRING_TABLES[name][0]:05X}", "Id": i, "字串": s}
            for name in STRING_TABLES for i, s in enumerate(rom.string_table(name))]


def battle_rows(rom: Rom) -> list[dict]:
    return [{"Id": f, "LZ entry": BATTLE_FIRST + f, "用途": FIELD_USE[f], "Unknown尾byte": rom.battle_tail(f)}
            for f in range(BATTLE_COUNT)]


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
    w, h, rgb = rom.map_rgb()
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(os.path.join(out, "map.png"))
    half = im.resize((w // 2, h // 2), Image.LANCZOS)
    dr = ImageDraw.Draw(half)
    castles = rom.castles()

    def centre(c: dict) -> tuple[int, int]:
        bx, by = c["block"]
        return (bx * BLOCK + c["cell"] % BLOCK) * 8 + 8, (by * BLOCK + c["cell"] // BLOCK) * 8 + 4

    for c in castles:
        for n in c["neighbours"]:
            if n > c["id"]:
                dr.line([*centre(c), *centre(castles[n])], fill=(255, 220, 0), width=1)
    f = font(12)
    for c in castles:
        x, y = centre(c)
        dr.rectangle([x - 8, y - 4, x + 8, y + 4], outline="red", width=2)
        dr.text((x + 10, y), f"{c['id']} {c['name']}", fill="white", anchor="lm", font=f, stroke_width=2,
                stroke_fill="black")
    half.save(os.path.join(out, "map_castles.png"))


def battle_images(rom: Rom, out: str) -> None:
    d = os.path.join(out, "battle")
    os.makedirs(d, exist_ok=True)
    for f in range(BATTLE_COUNT):
        w, h, rgb = rom.battle_rgb(f)
        png(w, h, rgb, os.path.join(d, f"{f:02d}.png"))


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
    ap = argparse.ArgumentParser(description="匯出 SFC 太閤立志伝 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    persons = rom.persons()

    sheets = {"名表": name_rows(rom), "人物": person_rows(rom, persons), "勢力": faction_rows(rom, persons),
              "城": castle_rows(rom, persons), "字串表": string_rows(rom), "戰場": battle_rows(rom)}
    names = ("names", "persons", "factions", "castles", "strings", "battle_fields")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "taikou.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p in persons:
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["face"]),
            os.path.join(faces, f"{p['record']:03d}_{full_name(p)}.png"))
    for n in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"{n:03d}.png"))
    map_images(rom, args.out)
    battle_images(rom, args.out)
    font_sheet(rom, os.path.join(args.out, "font.png"))
    print(f"頭像 {len(persons)} 人＋{PORTRAIT_COUNT} 張、大地圖、戰場 {BATTLE_COUNT} 張、字型 → {args.out}")


if __name__ == "__main__":
    main()
