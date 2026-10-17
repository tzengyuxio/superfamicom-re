#!/usr/bin/env python3
"""匯出 SFC ウイニングポスト2 的現役馬、種牡馬、繁殖牝馬、幼駒、騎手、調教師、馬主、牧場、秘書、比賽、日程、名稱表、頭像與字型。

Usage: .venv/bin/python winning2/export.py [--rom ROM] [--out DIR] [--scale N]

Writes racehorses.csv, stallions.csv, mares.csv, foals.csv, jockeys.csv, trainers.csv, owners.csv, farms.csv,
secretaries.csv, races.csv, schedule.csv, name_tables.csv (+ winning2.xlsx), faces/ + faces.png (face codes
0-207, Program '96 0-234), font.png. Program '96 (--rom) goes to output/program96/ (Rev 1: output/program96_rev1/) unless --out is given.
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import DEFAULT_ROM, FACE_H, FACE_W, GLYPH_BYTES, GLYPH_H, GLYPH_W, Rom

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing


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
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        fields = list(dict.fromkeys(k for r in rows for k in r))
        ws.append(fields)
        for r in rows:
            ws.append([r.get(k, "") for k in fields])
    wb.save(path)


def sheets(rom: Rom) -> dict[str, list[dict]]:
    jockeys = rom.jockeys()

    def jname(i) -> str:
        return jockeys[i]["name"] if isinstance(i, int) and i < len(jockeys) else ""

    sched = rom.schedule()
    when = {}
    for e in sched:
        when.setdefault(e["race"], []).append(f"{e['month']}月{e['week']}週{e['day']} {e['course']}{e['race_no']}R")
    races = [{**r, "when": " / ".join(when.get(r["race"], []))} for r in rom.races()]
    return {
        "racehorses": rom.racehorses(),
        "stallions": rom.stallions(),
        "mares": rom.mares(),
        "foals": rom.foals(),
        "jockeys": jockeys,
        "trainers": [{**t, "jockey_name": jname(t["jockey"]), "jockey2_name": jname(t["jockey2"])}
                     for t in rom.trainers()],
        "owners": rom.owners(),
        "farms": rom.farms(),
        "secretaries": rom.secretaries(),
        "races": races,
        "schedule": sched,
        "name_tables": [{"table": k, "index": i, "text": s} for k, v in rom.string_tables().items()
                        for i, s in enumerate(v)],
    }


def save_rgb(px: list[list[tuple]], path: str, scale: int) -> Image.Image:
    im = Image.new("RGB", (len(px[0]), len(px)))
    im.putdata([c for row in px for c in row])
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(path)
    return im


def export_faces(rom: Rom, out: str, scale: int) -> int:
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    labels = {}
    for s in rom.secretaries():
        labels.setdefault(s["face"], s["surname"])
    for kind in ("trainers", "jockeys", "owners"):
        for p in getattr(rom, kind)()[:61]:
            if isinstance(p.get("face"), int):
                labels.setdefault(p["face"], p["surname"] + p["given"])
    w, h = FACE_W * 8, FACE_H * 8
    cols = 16
    sheet = Image.new("RGB", (cols * (w + 4) * scale, ((rom.face_count + cols - 1) // cols) * (h + 14) * scale),
                      (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for code in range(rom.face_count):
        im = save_rgb(rom.face_rgb(code), os.path.join(out, "faces", f"face_{code:03d}.png"), scale)
        x, y = (code % cols) * (w + 4) * scale, (code // cols) * (h + 14) * scale
        sheet.paste(im, (x, y))
        label = f"{code} {labels.get(code, '')}"
        size = 10 * scale
        while size > 6 and draw.textlength(label, font=font(size)) > (w + 3) * scale:
            size -= 1
        draw.text((x, y + h * scale + 1), label, fill=(255, 255, 255), font=font(size))
    sheet.save(os.path.join(out, "faces.png"))
    return rom.face_count


def export_font(rom: Rom, out: str) -> None:
    """Every glyph, 32 per row, in code order (code 0x8140 + n): 12x12, 1 bit per pixel, big-endian bit stream."""
    cols, cell = 32, GLYPH_W + 2
    n = rom.glyph_count
    im = Image.new("L", (cols * cell, ((n + cols - 1) // cols) * cell), 255)
    for g in range(n):
        o = rom.glyph_offset(0x8140 + g)
        v = int.from_bytes(rom.data[o:o + GLYPH_BYTES], "big")
        x0, y0 = (g % cols) * cell, (g // cols) * cell
        for p in range(GLYPH_W * GLYPH_H):
            if v >> (GLYPH_BYTES * 8 - 1 - p) & 1:
                im.putpixel((x0 + p % GLYPH_W, y0 + p // GLYPH_W), 0)
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(out, "font.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out")
    ap.add_argument("--scale", type=int, default=2, help="頭像放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    sub = "" if rom.version == "original" else rom.version + (f"_rev{rom.revision}" if rom.revision else "")
    out = args.out or os.path.join(HERE, "output", sub)
    os.makedirs(out, exist_ok=True)
    data = sheets(rom)
    for name, rows in data.items():
        write_csv(rows, os.path.join(out, name + ".csv"))
    write_xlsx(data, os.path.join(out, "winning2.xlsx"))
    n_faces = export_faces(rom, out, args.scale)
    export_font(rom, out)
    for name, rows in data.items():
        print(f"{name}.csv: {len(rows)} rows")
    print(f"faces: {n_faces}; font {rom.glyph_count} glyphs -> {out} ({rom.version})")


if __name__ == "__main__":
    main()
