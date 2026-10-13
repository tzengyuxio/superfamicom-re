#!/usr/bin/env python3
"""匯出 SFC スーパー蒼き狼と白き牝鹿・元朝秘史 的人物、國、王家、女性、兵科、交易品、頭像與地圖。

Usage: .venv/bin/python genchou/export.py [--rom ROM] [--out DIR]

Writes persons.csv (the 4 scenarios), family.csv, women.csv, countries.csv, houses.csv, regions.csv (names and
label positions), units.csv, goods.csv (trade table), battle_maps.csv, battle_cells.csv (+ genchou.xlsx when
openpyxl is installed), faces/ (one PNG per scenario person and woman), portraits/ (00-96), heads/ (the 56
composed-face heads, both versions of every part), map_mongol.png / map_world.png (+ _labels: region numbers
and names), battle/ (the 47 battle maps) and font.png (the 2046 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BATTLE_COUNT,
    BATTLE_ENTRY,
    BATTLE_H,
    BATTLE_TILE_H,
    BATTLE_TILE_W,
    BATTLE_TILESET_ENTRY,
    BATTLE_W,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    GLYPH_COUNT,
    GRADES,
    MAP_H,
    MAP_W,
    MONGOL_COUNTRIES,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    TERRAIN_NAMES,
    UNIT_CLASSES,
    WOMAN_PORTRAIT,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
STATUS = {3: "国王", 2: "領主(推測)", 1: "家臣", 0: "在野"}


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def face_label(code: int, woman: bool = False) -> str:
    if not code & 0x8000:
        return f"專屬 {code + (WOMAN_PORTRAIT if woman else 0):02d}"
    f = Rom.face_fields(code)
    return f"組合 頭{f['head']} " + "".join(map(str, f["variants"]))


def names(rom: Rom, sc: int) -> tuple[list[str], dict[int, str]]:
    regions = rom.region_names(sc > 0)
    return regions, {h["id"]: h["name"] for h in rom.houses(sc)}


def person_row(rom: Rom, p: dict, regions: list[str], houses: dict[int, str], cultures: list[str]) -> dict:
    return {"記錄": p["slot"], "姓名": p["name"], "王家": houses.get(p["house"], "") if p["house"] != 0xFF else "",
            "所在國": regions[p["country"]] if p["country"] < len(regions) else p["country"],
            "身分": STATUS.get(p["status"], p["status"]), "體力": p["hp"], "體力上限": p["hp_max"],
            "戦闘": GRADES[p["戦闘"]], "政治": GRADES[p["政治"]], "魅力": GRADES[p["魅力"]], "指揮": GRADES[p["指揮"]],
            "年齢": p["age"], "文化(推測)": cultures[p["culture"]], "頭像碼": f"{p['face']:04X}",
            "頭像": face_label(p["face"]), "Unknown22(其他bits)": f"{p['unknown22']:02X}"}


def person_rows(rom: Rom) -> list[dict]:
    cultures, rows = rom.culture_names(), []
    for sc in range(SCENARIO_COUNT):
        regions, houses = names(rom, sc)
        for p in rom.persons(sc):
            rows.append({"劇本": sc + 1, "年": rom.year(sc), **person_row(rom, p, regions, houses, cultures)})
    return rows


def family_rows(rom: Rom) -> list[dict]:
    regions, houses = names(rom, 0)
    return [person_row(rom, p, regions, houses, rom.culture_names()) for p in rom.family()]


def women_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        regions = rom.region_names(sc > 0)
        for w in rom.women(sc):
            rows.append({"劇本": sc + 1, "記錄": w["slot"], "姓名": w["name"],
                         "所在國": regions[w["country"]] if w["country"] < len(regions) else w["country"],
                         "頭像碼": f"{w['face']:04X}", "頭像": face_label(w["face"], True),
                         "Unknown15": w["unknown15"], "Unknown16": w["unknown16"], "Unknown17": w["unknown17"]})
    return rows


def country_rows(rom: Rom) -> list[dict]:
    units = [u["name"] for u in rom.units()]
    rows = []
    for sc in range(SCENARIO_COUNT):
        regions, _ = names(rom, sc)
        owner = {c: h["name"] for h in rom.houses(sc) for c in h["countries"]}
        for c in rom.countries(sc):
            r = c["raw"]
            rows.append({"劇本": sc + 1, "Id": c["id"], "編號": c["id"] + 1, "名": regions[c["id"]],
                         "王家": owner.get(c["id"], ""), "相鄰": "、".join(regions[n] for n in c["neighbours"]),
                         "金": c["gold"], "食糧": c["food"], "人口": c["population"],
                         "住民配分(農業 牧畜 特産 街)": " ".join(map(str, c["split"])),
                         "Unknown19": r[19], "畫面值+20": r[20], "畫面值+21": r[21], "畫面值+22": r[22],
                         "部隊(推測)": "、".join(f"{units[k]}{n}" for k, n in enumerate(c["units"]) if n),
                         "Unknown39_40": f"{r[39]} {r[40]}", "Flag41": r[41], "Unknown42_43": f"{r[42]:02X} {r[43]:02X}",
                         "住民配分2(推測)": " ".join(map(str, c["split2"])), "Unknown48_49": f"{r[48]} {r[49]}"})
    return rows


def house_rows(rom: Rom) -> list[dict]:
    rows, cultures = [], rom.culture_names()
    for sc in range(SCENARIO_COUNT):
        regions, _ = names(rom, sc)
        persons = {p["slot"]: p["name"] for p in rom.persons(sc)}
        for h in rom.houses(sc):
            rows.append({"劇本": sc + 1, "Id": h["id"], "名": h["name"], "國王": persons.get(h["ruler"], ""),
                         "國數": len(h["countries"]), "國": "、".join(regions[c] for c in h["countries"]),
                         "Unknown23(文化?)": f"{h['unknown23']} {cultures[h['unknown23']] if h['unknown23'] < 8 else ''}"})
    return rows


def region_rows(rom: Rom) -> list[dict]:
    rows = []
    for world in (False, True):
        for k, (name, (x, y)) in enumerate(zip(rom.region_names(world), rom.region_positions(world))):
            rows.append({"地圖": "世界" if world else "モンゴル", "Id": k, "編號": k + 1, "名": name,
                         "標籤x": x, "標籤y": y, "戰場圖": k + (MONGOL_COUNTRIES if world else 0),
                         "戰場圖塊": BATTLE_TILESET_ENTRY + rom.battle_tileset(k + (MONGOL_COUNTRIES if world else 0))})
    return rows


def unit_rows(rom: Rom) -> list[dict]:
    return [{"Id": u["id"], "名": u["name"], "分類": UNIT_CLASSES[u["class"]], "戦意": u["morale"], "機動": u["mobility"],
             "近接": GRADES[u["melee"]], "突撃": GRADES[u["charge"]],
             "矢弾": GRADES[u["missile"]] if u["missile"] < 5 else "-", "防御": GRADES[u["defense"]],
             "特殊": "" if u["special"] == 0xFF else u["special"], "徴兵価格": u["price"], "電腦優先順": u["com_rank"]}
            for u in rom.units()]


def goods_rows(rom: Rom) -> list[dict]:
    merchants, table = rom.merchant_names(), rom.trade_table()
    return [{"Id": g, "名": name, **{f"{m}(推測價格)": table[k][g] for k, m in enumerate(merchants)}}
            for g, name in enumerate(rom.goods_names())]


def battle_name(rom: Rom, n: int) -> str:
    world = n >= MONGOL_COUNTRIES
    return rom.region_names(world)[n - MONGOL_COUNTRIES if world else n]


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for n in range(BATTLE_COUNT):
        terrain = rom.battle_terrain(n)
        entries = rom.battle_entries(n)
        rows.append({"Id": n, "LZ": BATTLE_ENTRY + n, "國": battle_name(rom, n),
                     "圖塊": BATTLE_TILESET_ENTRY + rom.battle_tileset(n), "城格": terrain.count(1),
                     "街格": terrain.count(2), "出入口格": sum(e is not None for e in entries)})
    return rows


def cell_rows(rom: Rom) -> list[dict]:
    rows = []
    for n in range(BATTLE_COUNT):
        world = n >= MONGOL_COUNTRIES
        regions = rom.region_names(world)
        for k, (t, e) in enumerate(zip(rom.battle_terrain(n), rom.battle_entries(n))):
            rows.append({"地圖": n, "x": k % BATTLE_W, "y": k // BATTLE_W, "地形": TERRAIN_NAMES.get(t, t),
                         "出入口(相鄰國)": "" if e is None else regions[e]})
    assert len(rows) == BATTLE_COUNT * BATTLE_W * BATTLE_H
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
    f = font(14)
    for world, tag in ((False, "mongol"), (True, "world")):
        im = Image.new("RGB", (w, h))
        im.putdata(rom.map_rgb(world))
        im.save(os.path.join(out, f"map_{tag}.png"))
        big = im.resize((w * 4, h * 4), Image.NEAREST)
        dr = ImageDraw.Draw(big)
        for k, (name, (x, y)) in enumerate(zip(rom.region_names(world), rom.region_positions(world))):
            dr.text((x * 4 + 36, y * 4 + 16), name, fill="white", anchor="lm", font=f, stroke_width=3,
                    stroke_fill="black")
        big.save(os.path.join(out, f"map_{tag}_labels.png"))


def head_sheet(rom: Rom, path: str) -> None:
    """Per head: the face with all parts at version 0, then at version 1."""
    fw, fh = FACE_W * 8, FACE_H * 8
    im = Image.new("RGB", (14 * (fw + 2), 8 * (fh + 2)), "white")
    for head in range(56):
        culture, n = divmod(head, 7)
        for v in range(2):
            code = 0x8000 | culture << 12 | n << 9 | (0x1F0 if v else 0)
            face = Image.new("RGB", (fw, fh))
            face.putdata(rom.face_rgb(code))
            im.paste(face, ((2 * n + v) * (fw + 2), culture * (fh + 2)))
    im.save(path)


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
    ap = argparse.ArgumentParser(description="匯出 SFC 元朝秘史資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "家族": family_rows(rom), "女性": women_rows(rom), "國": country_rows(rom),
              "王家": house_rows(rom), "地域": region_rows(rom), "兵科": unit_rows(rom), "交易品": goods_rows(rom),
              "戰場": battle_rows(rom), "戰場格": cell_rows(rom)}
    files = ("persons", "family", "women", "countries", "houses", "regions", "units", "goods", "battle_maps",
             "battle_cells")
    for rows, fn in zip(sheets.values(), files):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "genchou.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    count = 0
    for sc in range(SCENARIO_COUNT):
        for p in rom.persons(sc):
            png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["face"]),
                os.path.join(faces, f"s{sc + 1}_{p['slot']:03d}_{p['name']}.png"))
            count += 1
        for w in rom.women(sc):
            png(FACE_W * 8, FACE_H * 8, rom.face_rgb(w["face"], True),
                os.path.join(faces, f"s{sc + 1}_w{w['slot']:02d}_{w['name']}.png"))
            count += 1
    for n in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"{n:02d}.png"))
    head_sheet(rom, os.path.join(args.out, "heads.png"))
    map_images(rom, args.out)
    battle = os.path.join(args.out, "battle")
    os.makedirs(battle, exist_ok=True)
    for n in range(BATTLE_COUNT):
        png(BATTLE_TILE_W * 8, BATTLE_TILE_H * 8, rom.battle_rgb(n),
            os.path.join(battle, f"{n:02d}_{battle_name(rom, n)}.png"))
    font_sheet(rom, os.path.join(args.out, "font.png"))
    print(f"頭像 {count} 張＋專屬 {PORTRAIT_COUNT} 張、組合臉頭 56 個、大地圖 2 張、戰場 {BATTLE_COUNT} 張、字型 → {args.out}")


if __name__ == "__main__":
    main()
