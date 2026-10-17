#!/usr/bin/env python3
"""匯出 SFC スーパー麻雀大会 的對手、台詞、情境、役名與頭像。

Usage: .venv/bin/python mahjong/export.py [--rom ROM] [--out DIR]

Writes persons.csv (21 opponents), dialogue.csv (21 x 133 lines), situations.csv (66), yaku.csv (52)
(+ mahjong.xlsx when openpyxl is installed), faces/ (7 PNG per opponent: faces 0-5 and the 56x56 image),
faces.png (all of them on one sheet) and names.png (the 21 name graphics).
"""
import argparse
import csv
import os
import sys

from PIL import Image
from rom import DEFAULT_ROM, FACE_COUNT, FACE_LABELS, NAME_H, NAME_W, PERSON_COUNT, SPECIAL_LABEL, SPECIAL_W, Rom

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = FACE_LABELS + [SPECIAL_LABEL]


def image(w: int, h: int, rgb: list[tuple[int, int, int]]) -> Image.Image:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    return im


def face_image(rom: Rom, i: int, k: int) -> Image.Image:
    w, h = rom.face_size(k)
    return image(8 * w, 8 * h, rom.face_rgb(i, k))


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.persons():
        pr = p["params"]
        row = {"Id": p["id"], "名前": p["name"], "読み": p["reading"], "[EXT]出典": p["origin"],
               "頭像調色盤": p["palette"], "頭像Stream": f"{p['face_stream']:06X}",
               "台詞Stream": f"{p['dialogue_stream']:06X}", "參數(原始)": pr["raw"].hex(" ").upper()}
        row.update({f"N{k:02d}": v for k, v in enumerate(pr["nibbles"])})
        row.update({f"F{k}": v for k, v in enumerate(pr["flags"])})
        rows.append(row)
    return rows


def situation_rows(rom: Rom) -> list[dict]:
    """With the first line of 織田信長 and of 朝香えり as samples (the meaning of a situation is not decoded)."""
    d0, d15 = rom.dialogue(0), rom.dialogue(15)
    return [{"情境": s["id"], "起始行": s["first"], "行數": s["count"], "機率n": s["chance"], "Flags": f"{s['flags']:02X}",
             "例(織田信長)": d0[s["first"]]["text"].replace("\n", " "),
             "例(朝香えり)": d15[s["first"]]["text"].replace("\n", " ")} for s in rom.situations()]


def dialogue_rows(rom: Rom) -> list[dict]:
    situ = {n: s["id"] for s in rom.situations() for n in range(s["first"], s["first"] + s["count"])}
    rows = []
    for p in rom.persons():
        for d in rom.dialogue(p["id"]):
            top, _, bottom = d["text"].partition("\n")
            rows.append({"Id": p["id"], "名前": p["name"], "行": d["line"], "情境": situ.get(d["line"], ""),
                         "表情碼": d["face_code"], "表情": LABELS[d["face"]] if d["face"] is not None else "",
                         "上段": top, "下段": bottom, "字碼": d["codes"].hex(" ").upper()})
    return rows


def yaku_rows(rom: Rom) -> list[dict]:
    return [{"Id": y["id"], "役名": y["name"], "字碼": y["codes"].hex(" ").upper()} for y in rom.yaku()]


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


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC スーパー麻雀大会 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"對手": person_rows(rom), "台詞": dialogue_rows(rom), "情境": situation_rows(rom), "役": yaku_rows(rom)}
    for rows, fn in zip(sheets.values(), ("persons", "dialogue", "situations", "yaku")):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "mahjong.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    cell = 8 * SPECIAL_W + 4
    sheet = Image.new("RGB", (cell * (FACE_COUNT + 1), cell * PERSON_COUNT), (40, 40, 40))
    names = Image.new("RGB", (8 * NAME_W, 8 * NAME_H * PERSON_COUNT))
    for p in rom.persons():
        i = p["id"]
        for k in range(FACE_COUNT + 1):
            im = face_image(rom, i, k)
            im.save(os.path.join(faces, f"{i:02d}_{k}_{p['name']}_{LABELS[k].replace(' ', '')}.png"))
            sheet.paste(im, (k * cell + 2, i * cell + 2))
        names.paste(image(8 * NAME_W, 8 * NAME_H, rom.name_rgb(i)), (0, 8 * NAME_H * i))
    sheet.save(os.path.join(args.out, "faces.png"))
    names.save(os.path.join(args.out, "names.png"))
    print(f"頭像 {PERSON_COUNT} 人 × {FACE_COUNT + 1} 張、faces.png、names.png → {args.out}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
