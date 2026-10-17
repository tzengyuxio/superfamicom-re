#!/usr/bin/env python3
"""匯出 SFC ウイニングポスト 的人物、馬主、調教師、騎手、馬（現役馬／種牡馬／繁殖牝馬）、馬名表、比賽、日程、名稱表、頭像與字型。

Usage: .venv/bin/python winning/export.py [--rom ROM] [--out DIR] [--scale N]

Writes persons.csv, owners.csv, trainers.csv, jockeys.csv, horses.csv, stallions.csv, mares.csv,
name_templates.csv, foreign_names.csv, fixed_names.csv, races.csv, calendar.csv, tracks.csv, name_tables.csv
(+ winning.xlsx), faces/ + faces.png (portraits 0x00-0xCF and the owners' composed faces), font.png.
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    GLYPH_COUNT,
    GRADED_COUNT,
    MARE_ID,
    PORTRAIT_COUNT,
    STALLION_ID,
    TRAINER_TRAIT_LABELS,
    Rom,
    glyph_offset,
)

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


def horse_rows(rom: Rom, rows: list[dict], kind: str) -> list[dict]:
    out = []
    for h in rows:
        if not h["used"]:
            continue
        out.append({"index": h["index"], "id": h["index"] + {"horse": 0, "mare": MARE_ID, "stallion": STALLION_ID}[kind],
                    "name": h["name"], "name_word": f"{h['name_word']:04X}",
                    "sire": h["sire"] if h["sire"] != 0xFFFF else "", "sire_name": rom.horse_label(h["sire"]),
                    "dam": h["dam"] if h["dam"] != 0xFFFF else "", "dam_name": rom.horse_label(h["dam"]),
                    "data": h["data"]})
    return out


def sheets(rom: Rom) -> dict[str, list[dict]]:
    jockeys = rom.jockeys()
    cal = rom.calendar()
    slots = {}
    for e in cal:
        if e["race"] is not None:
            slots.setdefault(e["race"], []).append(e)
    races = []
    for r, name in enumerate(rom.race_names()):
        es = slots.get(r, [])
        races.append({"race": r, "name": name, "graded": r < GRADED_COUNT,
                      "nth_1997": rom.u16(rom.o["RACE_NTH"] + 2 * r) if r < GRADED_COUNT else "",
                      "class": "／".join(sorted({e["class_short"] for e in es})),
                      "slots": " ".join(str(e["slot"]) for e in es),
                      "when": " ".join(f"{e['month']}月{e['week']}週{'西' if e['west'] else '東'}" for e in es)})
    return {
        "persons": rom.persons(),
        "owners": [{"index": o["index"], "surname": o["surname"], "given": o["given"], "face": f"{o['face']:04X}",
                    "crown": o["crown"], "crown_after": o["crown_after"], "data": o["data"]} for o in rom.owners()],
        "trainers": [{"index": t["index"], "surname": t["surname"], "given": t["given"], "face": f"{t['face']:02X}",
                      "jockey": t["jockey"], "jockey_name": jockeys[t["jockey"]]["surname"] + jockeys[t["jockey"]]["given"],
                      **dict(zip(TRAINER_TRAIT_LABELS, t["trait_names"])), "data": t["data"]} for t in rom.trainers()],
        "jockeys": [{k: (f"{v:02X}" if k == "face" else v) for k, v in j.items()} for j in jockeys],
        "horses": horse_rows(rom, rom.horses(), "horse"),
        "stallions": horse_rows(rom, rom.stallions(), "stallion"),
        "mares": horse_rows(rom, rom.mares(), "mare"),
        "name_templates": rom.templates(),
        "foreign_names": rom.foreign_names(),
        "fixed_names": [{"index": n, "name": s} for n, s in enumerate(rom.fixed_names())],
        "races": races,
        "calendar": cal,
        "tracks": rom.tracks(),
        "name_tables": [{"table": k, "index": i, "text": s} for k, v in rom.name_tables().items() for i, s in enumerate(v)],
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
    faces = [(c, f"{c:02X}") for c in range(PORTRAIT_COUNT)]
    faces += [(o["face"], o["surname"] + o["given"]) for o in rom.owners()[:40]]
    w, h = FACE_W * 8, FACE_H * 8
    cols = 16
    sheet = Image.new("RGB", (cols * (w + 4) * scale, ((len(faces) + cols - 1) // cols) * (h + 14) * scale), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for n, (code, label) in enumerate(faces):
        name = f"face_{code:02X}" if code < PORTRAIT_COUNT else f"owner_{n - PORTRAIT_COUNT:02d}_{code:04X}"
        im = save_rgb(rom.face_rgb(code), os.path.join(out, "faces", name + ".png"), scale)
        x, y = (n % cols) * (w + 4) * scale, (n // cols) * (h + 14) * scale
        sheet.paste(im, (x, y))
        size = 10 * scale
        while size > 6 and draw.textlength(label, font=font(size)) > (w + 3) * scale:
            size -= 1
        draw.text((x, y + h * scale + 1), label, fill=(255, 255, 255), font=font(size))
    sheet.save(os.path.join(out, "faces.png"))
    return len(faces)


def export_font(rom: Rom, out: str) -> None:
    """All 2368 glyphs, 32 per row, in code order (code 0x8140 + n)."""
    cols = 32
    im = Image.new("L", (cols * 18, ((GLYPH_COUNT + cols - 1) // cols) * 18), 255)
    for n in range(GLYPH_COUNT):
        o = glyph_offset(0x8140 + n)
        x0, y0 = (n % cols) * 18, (n // cols) * 18
        for t in range(4):
            for y in range(8):
                b = rom.data[o + 8 * t + y]
                for x in range(8):
                    if b >> (7 - x) & 1:
                        im.putpixel((x0 + (t & 1) * 8 + x, y0 + (t >> 1) * 8 + y), 0)
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(out, "font.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2, help="頭像放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    data = sheets(rom)
    for name, rows in data.items():
        write_csv(rows, os.path.join(args.out, name + ".csv"))
    write_xlsx(data, os.path.join(args.out, "winning.xlsx"))
    n_faces = export_faces(rom, args.out, args.scale)
    export_font(rom, args.out)
    for name, rows in data.items():
        print(f"{name}.csv: {len(rows)} rows")
    print(f"faces: {n_faces}; font {GLYPH_COUNT} glyphs -> {args.out}")


if __name__ == "__main__":
    main()
