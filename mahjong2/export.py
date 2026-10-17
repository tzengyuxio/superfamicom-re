#!/usr/bin/env python3
"""匯出 SFC 麻雀大会II 的對手、台詞、情境、役名、規則、雀荘、系統訊息與頭像。

Usage: .venv/bin/python mahjong2/export.py [--rom ROM] [--out DIR]

Writes persons.csv (26 opponents), dialogue.csv (26 x 344 lines), situations.csv (103), yaku.csv (65 names),
rules.csv (44 items), parlors.csv (7), messages.csv (71) (+ mahjong2.xlsx when openpyxl is installed), faces/ (9 PNG
per opponent), faces.png (all of them on one sheet) and names.png (the 26 name graphics).
"""
import argparse
import csv
import os
import sys

from PIL import Image
from rom import (
    DEFAULT_ROM,
    FACE_IMAGES,
    FACE_LABELS,
    NAME_H,
    NAME_W,
    PARLOR_COUNT,
    PERSONS,
    PROFILE_MESSAGE,
    YAKU_COUNT,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PARLOR_MESSAGE = 16   # messages 16-22 describe the parlors 0-6
PARLOR_NAMES = ["あなたのいえ", "じゃんそう ゆう", "ふじみそう", "あおいりょかん", "あんこくじ", "ロイヤル", "じゃんそう はぎ"]


def image(w: int, h: int, rgb: list[tuple[int, int, int]]) -> Image.Image:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    return im


def face_image(rom: Rom, p: int, k: int) -> Image.Image:
    w, h = rom.face_size(k)
    return image(8 * w, 8 * h, rom.face_rgb(p, k))


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.persons():
        pr = p["params"]
        row = {"Id": p["id"], "名前": p["name"], "読み": p["reading"], "[EXT]出典": p["origin"],
               "雀荘": "全部" if p["parlor"] == 0 else ("大会のみ" if p["parlor"] is None else PARLOR_NAMES[p["parlor"]]),
               "頭像調色盤": p["palette"], "怒調色盤": p["big_palette"], "頭像Stream": f"{p['face_stream']:06X}",
               "台詞Stream": f"{p['dialogue_stream']:06X}", "參數(原始)": pr["raw"].hex(" ").upper()}
        row.update({f"N{k:02d}": v for k, v in enumerate(pr["nibbles"])})
        row.update({f"F{k}": v for k, v in enumerate(pr["flags"])})
        row["紹介"] = p["profile"].replace("\n", "")
        rows.append(row)
    return rows


def situation_rows(rom: Rom) -> list[dict]:
    """With the first line of リンカーン and of 卑弥呼 as samples (the meaning of a situation is not decoded)."""
    d2, d20 = rom.dialogue(2), rom.dialogue(20)
    return [{"情境": s["id"], "起始行": s["first"], "行數": s["count"], "機率n": s["chance"], "Flags": f"{s['flags']:02X}",
             "例(リンカーン)": d2[s["first"]]["text"].replace("\n", " "),
             "例(卑弥呼)": d20[s["first"]]["text"].replace("\n", " ")} for s in rom.situations()]


def dialogue_rows(rom: Rom) -> list[dict]:
    situ = {n: s["id"] for s in rom.situations() for n in range(s["first"], s["first"] + s["count"])}
    rows = []
    for p in rom.persons():
        for d in rom.dialogue(p["id"]):
            lines = (d["text"].split("\n") + ["", "", ""])[:3]
            rows.append({"Id": p["id"], "名前": p["name"], "行": d["line"], "情境": situ.get(d["line"], ""),
                         "表情碼": d["face_code"], "表情": FACE_LABELS[d["face"]] if d["face"] is not None else "",
                         "第1行": lines[0], "第2行": lines[1], "第3行": lines[2], "字碼": d["codes"].hex(" ").upper()})
    return rows


def yaku_rows(rom: Rom) -> list[dict]:
    kinds = {range(YAKU_COUNT): "役", range(54, 59): "點數", range(59, 60): "流局", range(60, 65): "途中流局"}
    return [{"Id": y["id"], "名稱": y["name"], "種類": next(v for r, v in kinds.items() if y["id"] in r),
             "字碼": y["codes"].hex(" ").upper()} for y in rom.yaku()]


def rule_rows(rom: Rom) -> list[dict]:
    rows = []
    for it in rom.rule_items():
        row = {"Id": it["id"], "項目": it["name"], "選項數": it["count"], "選項": " / ".join(it["labels"]),
               "標準": it["labels"][it["standard"]]}
        for k in range(PARLOR_COUNT):
            v = rom.parlor_rules(k)[it["id"]]
            row[PARLOR_NAMES[k]] = it["labels"][v] if v < it["count"] else f"{rom.starting_points(v):,}"
        rows.append(row)
    deps = {b: a for a, b in rom.rule_deps()}
    items = rom.rule_items()
    for row in rows:
        row["前提項目"] = items[deps[row["Id"]]]["name"] if row["Id"] in deps else ""
    return rows


def parlor_rows(rom: Rom) -> list[dict]:
    names = {p["id"]: p["name"] for p in rom.persons()}
    items = rom.rule_items()
    return [{"Id": k, "名稱": PARLOR_NAMES[k],
             "固定キャラ": "、".join(names[p] for p in PERSONS if rom.parlor(p) == k and k),
             "對手": "、".join(names[p] for p in rom.parlor_persons(k)),
             "固定規則": "、".join(f"{items[i]['name']}={items[i]['labels'][v] if v < items[i]['count'] else rom.starting_points(v)}"
                               for i, v in rom.rule_overrides(k)) if k != 1 else "（標準ルール）",
             "說明": rom.message_text(PARLOR_MESSAGE + k).replace("\n", "")} for k in range(PARLOR_COUNT)]


def message_rows(rom: Rom) -> list[dict]:
    rows = []
    for n in range(1, 72):
        head = rom.message_raw(n)[0]
        rows.append({"No": n, "標頭": head.hex(" ").upper(), "內容": rom.message_text(n).replace("\n", "⏎"),
                     "備註": f"{rom.persons()[n - PROFILE_MESSAGE - 1]['name']} の紹介" if n > PROFILE_MESSAGE else ""})
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


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 麻雀大会II 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"對手": person_rows(rom), "台詞": dialogue_rows(rom), "情境": situation_rows(rom), "役": yaku_rows(rom),
              "規則": rule_rows(rom), "雀荘": parlor_rows(rom), "訊息": message_rows(rom)}
    names = ("persons", "dialogue", "situations", "yaku", "rules", "parlors", "messages")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "mahjong2.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    n = len(FACE_IMAGES)
    cell = 8 * 7 + 4
    sheet = Image.new("RGB", (cell * n, cell * len(PERSONS)), (40, 40, 40))
    names_im = Image.new("RGB", (8 * NAME_W, 8 * NAME_H * len(PERSONS)))
    for p in rom.persons():
        i = p["id"]
        for k in range(n):
            im = face_image(rom, i, k)
            im.save(os.path.join(faces, f"{i:02d}_{k}_{p['name']}_{FACE_LABELS[k].replace(' ', '')}.png"))
            sheet.paste(im, (k * cell + 2, (i - 1) * cell + 2))
        names_im.paste(image(8 * NAME_W, 8 * NAME_H, rom.name_rgb(i)), (0, 8 * NAME_H * (i - 1)))
    sheet.save(os.path.join(args.out, "faces.png"))
    names_im.save(os.path.join(args.out, "names.png"))
    print(f"頭像 {len(PERSONS)} 人 × {n} 張、faces.png、names.png → {args.out}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
