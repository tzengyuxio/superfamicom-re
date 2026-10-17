#!/usr/bin/env python3
"""匯出 SFC リーディングカンパニー 的協議會、廠商、產品、機能、等級、販促、劇本開局狀態、頭像與街區地圖。

Usage: .venv/bin/python leading/export.py [--rom ROM] [--out DIR] [--scale N]

Writes formats.csv, makers.csv, products.csv, market_cells.csv, features.csv, grades.csv, promotions.csv,
files.csv (+ leading.xlsx), faces/ + faces.png, town_map.png, buildings.png.
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BUILDING_KINDS,
    BUILDING_PALETTE,
    BUILDING_VARIANTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_KINDS,
    FACE_W,
    LOT_COLUMNS,
    LOT_ROW,
    SCENARIO_COUNT,
    SCENARIO_YEARS,
    TOWN_PALETTE,
    TOWN_ROWS,
    Rom,
    render_tilemap,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
CONTRACT = {0: "original", 1: "license", 2: "OEM"}  # the strings the product sheet prints
STATE = {0: "開発中", 2: "発売中"}
# the scenario-1 opening town (verify_maps.py): lot -> (kind, level, variant)
OPENING_LOTS = [("LABO", 2, 2), ("LABO", 2, 2), ("FACT", 1, 1), ("BUSI", 2, 1)]


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def write_csv(rows: list[dict], path: str) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        return
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        fields = list(dict.fromkeys(k for r in rows for k in r))
        ws.append(fields)
        for r in rows:
            ws.append([r.get(k, "") for k in fields])
    wb.save(path)


def format_rows(rom: Rom) -> list[dict]:
    out = []
    for s in range(SCENARIO_COUNT):
        for f in rom.format_records(s):
            out.append({"scenario": s + 1, "years": SCENARIO_YEARS[s], "format": f["index"], "name": f["name"].upper(),
                        "present": int(f["present"]),
                        **{f"sales_q{k + 1}": f["sales"][k] for k in range(4)}})
    return out


def maker_rows(rom: Rom) -> list[dict]:
    fmts = rom.formats()
    out = []
    for s in range(SCENARIO_COUNT):
        prods = {(p["format"], p["slot"]): p["name"] for p in rom.products(s)}
        for m in rom.maker_records(s):
            out.append({"scenario": s + 1, "maker": m["index"], "name": m["name"].upper(),
                        "format": "" if m["format"] is None else fmts[m["format"]].upper(), "leader": m["leader"],
                        **{f"trust_{fmts[k]}": m["trust"][k] for k in range(4)},
                        "product": "" if m["product"] is None else prods[(m["format"], m["product"])].upper(),
                        "w14": m["w14"], "w16": m["w16"]})
    return out


def product_rows(rom: Rom) -> list[dict]:
    fmts, makers, grades = rom.formats(), rom.maker_names(), rom.grades()
    out = []
    for s in range(SCENARIO_COUNT):
        for p in rom.products(s):
            out.append({"scenario": s + 1, "format": fmts[p["format"]].upper(), "slot": p["slot"],
                        "name": p["name"].upper(), "state": STATE.get(p["state"], p["state"]),
                        "grade": grades[p["grade"]]["name"],
                        "cell": f"{p['grade']},{p['cell_col']}", "maker": makers[p["maker"]].upper(),
                        "contract": CONTRACT.get(p["contract"], p["contract"]), "rate": p["rate"],
                        "freshness": p["freshness"], "operating_rate": p["operating_rate"],
                        "awareness": p["awareness"], "raw_13_3e": p["raw"][0x13:].hex(" ")})
    return out


def cell_rows(rom: Rom) -> list[dict]:
    fmts = rom.formats()
    out = []
    for s in range(SCENARIO_COUNT):
        prods = {(p["format"], p["slot"]): p["name"] for p in rom.products(s)}
        for i, c in enumerate(rom.cells(s)):
            if c:
                out.append({"scenario": s + 1, "row_grade": i // 8, "col": i % 8,
                            "products": " / ".join(f"{fmts[f].upper()}:{prods[(f, p)].upper()}" for f, p in c)})
    return out


def feature_rows(rom: Rom) -> list[dict]:
    out = []
    for f in rom.features():
        st = [rom.feature_state(s)[f["index"]] for s in range(SCENARIO_COUNT)]
        out.append({"index": f["index"], "name": f["name"], "bit": f"{f['bit']:#06x}", "b18": f["b18"],
                    "w19": f["w19"], "w21": f["w21"], "w23": f["w23"],
                    **{f"scenario{s + 1}_state": st[s].hex(" ") for s in range(SCENARIO_COUNT)}})
    return out


def grade_rows(rom: Rom) -> list[dict]:
    return [{"index": g["index"], "name": g["name"], "price_thousand_yen": g["price"]} for g in rom.grades()]


def promotion_rows(rom: Rom) -> list[dict]:
    return [{"index": i, "name": n} for i, n in enumerate(rom.promotions())]


def file_rows(rom: Rom) -> list[dict]:
    return [{"index": f["index"], "name": f["name"], "bank": f"{f['bank']:02X}", "addr": f"{f['addr']:04X}",
             "offset": f"{f['offset']:#07x}", "size": f["size"], "lz_size": rom.is_lz(f) or ""}
            for f in rom.files()]


def save_rgb(pixels: list[list], path: str, bg=(0, 0, 0)) -> Image.Image:
    im = Image.new("RGB", (len(pixels[0]), len(pixels)))
    im.putdata([c or bg for row in pixels for c in row])
    im.save(path)
    return im


def export_faces(rom: Rom, out: str, scale: int) -> None:
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    faces = rom.faces()
    w, h = FACE_W * 8, FACE_H * 8
    cols = 12
    rows = len(FACE_KINDS)
    sheet = Image.new("RGB", (cols * (w + 4) * scale, rows * (h + 16) * scale), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    row_of = {}
    for f in faces:
        im = Image.new("RGB", (w, h))
        im.putdata([c for row in rom.face_rgb(f["kind"], f["image"]) for c in row])
        im.save(os.path.join(out, "faces", f"{f['file']}_{f['image']:02d}.png"))
        r = row_of.setdefault(f["kind"], f["kind"])
        x, y = f["image"] * (w + 4) * scale, r * (h + 16) * scale
        sheet.paste(im.resize((w * scale, h * scale), Image.NEAREST), (x, y))
        draw.text((x, y + h * scale + 1), f"{f['group']}{f['image']}", fill=(255, 255, 255), font=font(10 * scale // 2))
    sheet.save(os.path.join(out, "faces.png"))


def export_town(rom: Rom, out: str) -> None:
    town = rom.town_background()
    bg = render_tilemap(town["tilemap"], town["tiles"], {TOWN_PALETTE: town["palette"]}, 32, TOWN_ROWS)
    pal = rom.building_palette()
    for n, (kind, level, variant) in enumerate(OPENING_LOTS):
        tm = b"".join((BUILDING_PALETTE << 10 | i).to_bytes(2, "little") for i in range(36))
        b = render_tilemap(tm, rom.building(kind, level, variant), {BUILDING_PALETTE: pal}, 6, 6)
        for y in range(48):
            for x in range(48):
                if b[y][x]:
                    bg[LOT_ROW * 8 + y][LOT_COLUMNS[n] * 8 + x] = b[y][x]
    save_rgb(bg, os.path.join(out, "town_map.png"))
    # every building variant: rows BUSI / FACT / LABO x level, columns variant
    sheet = Image.new("RGB", (BUILDING_VARIANTS * 52 + 60, 15 * 52), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    tm = b"".join((BUILDING_PALETTE << 10 | i).to_bytes(2, "little") for i in range(36))
    for r, (kind, level) in enumerate((k, lv) for k in BUILDING_KINDS for lv in range(1, 6)):
        d.text((2, r * 52 + 18), f"{kind}_L{level}", fill=(255, 255, 255), font=font(11))
        for v in range(BUILDING_VARIANTS):
            px = render_tilemap(tm, rom.building(kind, level, v), {BUILDING_PALETTE: pal}, 6, 6)
            im = Image.new("RGB", (48, 48))
            im.putdata([c or (0, 0, 0) for row in px for c in row])
            sheet.paste(im, (60 + v * 52, r * 52 + 2))
    sheet.save(os.path.join(out, "buildings.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2, help="頭像總覽放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    sheets = {"formats": format_rows(rom), "makers": maker_rows(rom), "products": product_rows(rom),
              "market_cells": cell_rows(rom), "features": feature_rows(rom), "grades": grade_rows(rom),
              "promotions": promotion_rows(rom), "files": file_rows(rom)}
    for name, rows in sheets.items():
        write_csv(rows, os.path.join(args.out, name + ".csv"))
    write_xlsx(sheets, os.path.join(args.out, "leading.xlsx"))
    export_faces(rom, args.out, args.scale)
    export_town(rom, args.out)
    for name, rows in sheets.items():
        print(f"{name}.csv: {len(rows)} rows")
    print(f"faces: {len(rom.faces())}; town_map.png, buildings.png -> {args.out}")


if __name__ == "__main__":
    main()
