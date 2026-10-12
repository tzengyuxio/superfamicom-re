#!/usr/bin/env python3
"""匯出 SFC スーパー三國志II 的人物、劇本配置、州、相鄰、頭像、大地圖與戰場地圖。

Usage: .venv/bin/python san2/export.py [--rom ROM] [--out DIR] [--scale N]

Writes persons.csv, person_scenarios.csv (6 scenarios), provinces.csv (6 x 41), adjacency.csv
(+ san2.xlsx when openpyxl is installed), faces/ (one PNG per person), portraits/ (P001-P208),
map.png, battle_maps/ (41), province_hex.png, china_battle_map(_labeled).png, mob_parts.png and mob_parts/.
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw
from rom import (
    BATTLE_COLS,
    BATTLE_ROWS,
    COMPOSITE_SLOTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    MAP_H,
    MAP_W,
    PORTRAIT_COUNT,
    PROVINCE_COUNT,
    SCENARIO_COUNT,
    SCENARIO_YEARS,
    TERRAIN,
    Rom,
    bgr555_rgb,
    is_composite,
    load_kanji,
)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import parts_sheet

SIDES = ["西", "西南", "東南", "西北", "東北", "東"]  # adjacency slot 0-5, geographic (as in the FC version)


def png(w: int, h: int, rgb: list[tuple[int, int, int]], path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def names(rom: Rom) -> list[str]:
    kanji = load_kanji()
    return ["".join(kanji.get(c, "?") for c in p["kanji_codes"]) for p in rom.persons()]


def face_label(code: int) -> str:
    if not is_composite(code):
        return f"P{code:03d}"
    return f"組合 {code & 7}-" + "".join(str(code >> shift & 3) for _, _, shift in COMPOSITE_SLOTS) + f"／色 {code >> 13 & 3}"


def person_rows(rom: Rom) -> list[dict]:
    kanji = load_kanji()
    return [{
        "Id": p["id"], "ROM_Offset": f"0x{p['offset']:05X}",
        "[EXT]Name": "".join(kanji.get(c, "?") for c in p["kanji_codes"]),
        "Kanji_Codes": " ".join(f"{c:04X}" for c in p["kanji_codes"]),
        "Reading": p["reading"],
        "才智": p["int"], "戰力": p["war"], "號召": p["charm"],
        "義理": p["duty"], "人德": p["virtue"], "野望": p["ambition"], "相性": p["compat"],
        "親族": f"{p['kin']:04X}", "生年": p["born"], "登場年": rom.debut(p["id"]) or "",
        "Face": f"{p['face']:04X}", "頭像": face_label(p["face"]),
    } for p in rom.persons()]


def scenario_rows(rom: Rom) -> list[dict]:
    rows, nm, persons = [], names(rom), rom.persons()
    for sc in range(SCENARIO_COUNT):
        rulers = rom.faction_rulers(sc)
        for p in persons:
            pl = rom.placement(p["id"], sc)
            if not pl:
                continue
            faction = rom.province(sc, pl["province"] - 1)["faction"]
            lord = rulers.get(faction) if pl["status"] in ("君主", "武將") else None
            rows.append({"劇本": sc + 1, "年": SCENARIO_YEARS[sc], "Id": p["id"], "[EXT]Name": nm[p["id"]],
                         "身分": pl["status"], "州": pl["province"], "[EXT]君主": nm[lord] if lord is not None else "",
                         "忠誠": "" if pl["loyalty"] is None else pl["loyalty"], "兵士": pl["soldiers"],
                         "年齡": SCENARIO_YEARS[sc] - p["born"] + 1})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    rows, nm = [], names(rom)
    for sc in range(SCENARIO_COUNT):
        rulers = rom.faction_rulers(sc)
        for i in range(PROVINCE_COUNT):
            p = rom.province(sc, i)
            lord = rulers.get(p["faction"])
            rows.append({"劇本": sc + 1, "州": i + 1, "勢力": "" if p["faction"] is None else p["faction"],
                         "[EXT]君主": nm[lord] if lord is not None else "", "人口": p["population"],
                         "金": p["gold"], "兵糧": p["food"], "民忠": p["loyalty"], "土地": p["land"],
                         "治水": p["flood"], "馬": p["horses"], "信": p["trust"]})
    return rows


def adjacency_rows(rom: Rom) -> list[dict]:
    pos, rows = rom.hex_layout(), []
    for i, adj in enumerate(rom.adjacency(), 1):
        q, r = pos[i]
        terrain = [t for row in rom.battle_terrain(i - 1) for t in row]
        row = {"州": i, "六角 q": q, "六角 r": r}
        row.update({SIDES[d]: v or "" for d, v in enumerate(adj)})
        row.update({f"戰場{name}": terrain.count(t) for t, name in enumerate(TERRAIN)})
        rows.append(row)
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


def face_rgb(rom: Rom, code: int) -> list[tuple[int, int, int]]:
    pal = [bgr555_rgb(c) for c in rom.face_palettes()[rom.face_palette_number(code)]]
    return [pal[v] for v in rom.face_pixels(code)]


def province_hex(rom: Rom, path: str) -> None:
    """The 41 provinces on the hex lattice of the adjacency table, flat-topped hexes in the column layout
    of china_battle_map (province (q, r) in column -(q + r), row -r, every other column half a hex lower)."""
    size = 28
    cells = {i: (-(q + r), -r) for i, (q, r) in rom.hex_layout().items()}
    pts = {i: (c * size * 1.5, (row - c / 2) * size * 3 ** 0.5) for i, (c, row) in cells.items()}
    x0, y0 = min(x for x, _ in pts.values()), min(y for _, y in pts.values())
    im = Image.new("RGB", (int(max(x for x, _ in pts.values()) - x0) + 2 * size + 20,
                           int(max(y for _, y in pts.values()) - y0) + 2 * size + 20), "white")
    dr = ImageDraw.Draw(im)
    for i, (x, y) in pts.items():
        cx, cy = x - x0 + size + 10, y - y0 + size + 10
        dr.regular_polygon((cx, cy, size), 6, fill=(247, 216, 165), outline="black")
        dr.text((cx, cy), str(i), fill="black", anchor="mm")
    im.save(path)


def china_battle_map(rom: Rom, path: str, labeled_path: str, scale: int) -> None:
    """All 41 battle fields laid out like province_hex.png (the FC version's column layout: 41 -> 40 -> 31
    straight up, every other column half a field lower). Fields stack 24 tiles apart: the odd hex
    columns of a field stick half a hex into the field below."""
    fw, fh = 2 * BATTLE_COLS, 2 * BATTLE_ROWS
    cells = {i: (-(q + r), -r) for i, (q, r) in rom.hex_layout().items()}
    org = {i: (c * fw, row * fh - c * fh // 2) for i, (c, row) in cells.items()}
    x0, y0 = min(x for x, _ in org.values()), min(y for _, y in org.values())
    org = {i: ((x - x0) * 8, (y - y0) * 8) for i, (x, y) in org.items()}
    w = max(x for x, _ in org.values()) + fw * 8
    h = max(y for _, y in org.values()) + (fh + 1) * 8
    big = Image.new("RGB", (w, h))
    for i, (ox, oy) in org.items():
        fw_px, fh_px, rgb = rom.battle_pixels(i - 1)
        field = Image.new("RGB", (fw_px, fh_px))
        field.putdata(rgb)
        mask = Image.new("1", (fw_px, fh_px))  # only the hexes, not the gaps of the odd columns
        md = ImageDraw.Draw(mask)
        for c in range(BATTLE_COLS):
            md.rectangle([16 * c, 8 * (c % 2), 16 * c + 15, 8 * (c % 2) + 16 * BATTLE_ROWS - 1], fill=1)
        big.paste(field, (ox, oy), mask)
    big = big.resize((w * scale, h * scale), Image.NEAREST)
    big.save(path)
    dr = ImageDraw.Draw(big)
    for i, (ox, oy) in org.items():
        cx, cy = (ox + fw * 4) * scale, (oy + fh * 4 + 4) * scale
        dr.rectangle([cx - 12 * scale, cy - 7 * scale, cx + 12 * scale, cy + 7 * scale], fill="white")
        dr.text((cx, cy), str(i), fill="black", anchor="mm", font_size=10 * scale)
    big.save(labeled_path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC スーパー三國志II 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2, help="地圖 PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "劇本人物": scenario_rows(rom), "州": province_rows(rom),
              "相鄰": adjacency_rows(rom)}
    for rows, fn in zip(sheets.values(), ("persons", "person_scenarios", "provinces", "adjacency")):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "san2.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p, name in zip(rom.persons(), names(rom)):
        png(FACE_W * 8, FACE_H * 8, face_rgb(rom, p["face"]), os.path.join(faces, f"{p['id']:03d}_{name}.png"))
    for code in range(1, PORTRAIT_COUNT + 1):
        png(FACE_W * 8, FACE_H * 8, face_rgb(rom, code), os.path.join(portraits, f"P{code:03d}.png"))

    png(MAP_W * 8, MAP_H * 8, rom.map_pixels(), os.path.join(args.out, "map.png"), args.scale)
    bdir = os.path.join(args.out, "battle_maps")
    os.makedirs(bdir, exist_ok=True)
    for i in range(PROVINCE_COUNT):
        png(*rom.battle_pixels(i), os.path.join(bdir, f"{i + 1:02d}.png"), args.scale)
    province_hex(rom, os.path.join(args.out, "province_hex.png"))
    china_battle_map(rom, os.path.join(args.out, "china_battle_map.png"),
                     os.path.join(args.out, "china_battle_map_labeled.png"), args.scale)

    import export_kaodata
    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)
    print(f"頭像 {len(sheets['人物'])} 人＋專屬 {PORTRAIT_COUNT} 張；大地圖 {MAP_W * 8}×{MAP_H * 8}；"
          f"戰場 {PROVINCE_COUNT} 張 → {args.out}")


if __name__ == "__main__":
    main()
