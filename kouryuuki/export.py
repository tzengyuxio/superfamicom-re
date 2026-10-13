#!/usr/bin/env python3
"""匯出 SFC 項劉記 的人物、劇本人物、地點、軍隊與頭像。

Usage: .venv/bin/python kouryuuki/export.py [--rom ROM] [--out DIR]

Writes persons.csv, person_scenarios.csv (4 scenarios), places.csv (4 x 39), armies.csv
(+ kouryuuki.xlsx when openpyxl is installed), faces/ (one PNG per person), portraits/ (F00-F96)
and map_places.png (the 55 x 44 map cells: roads and places).
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from rom import (
    DEFAULT_ROM,
    DIPLOMACY,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    MAP_FEATURES,
    MAP_H,
    MAP_ROADS,
    MAP_W,
    SCENARIO_COUNT,
    SCENARIO_YEARS,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing


def png(w: int, h: int, rgb: list[tuple[int, int, int]], path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def lords(rom: Rom, sc: int) -> dict[int, str]:
    """勢力 -> 君主's name (the person of that 勢力 with flags & 7 == 0)."""
    return {p["faction"]: rom.persons()[p["id"]]["name"] for p in rom.scenario_persons(sc) if p["flags"] & 7 == 0}


def person_rows(rom: Rom) -> list[dict]:
    return [{"Id": p["id"], "ROM_Offset": f"0x{p['offset']:05X}", "姓名": p["name"], "読み": p["reading"],
             "生年(紀元前)": p["born"], "頭像": f"F{p['id']:02d}", "Unknown": p["unknown"]} for p in rom.persons()]


def scenario_rows(rom: Rom) -> list[dict]:
    persons = rom.persons()
    rows = []
    for sc in range(SCENARIO_COUNT):
        names = lords(rom, sc)
        armies = rom.scenario_armies(sc)
        for r in rom.scenario_persons(sc):
            p = persons[r["id"]]
            army = armies[r["army"]] if r["army"] < len(armies) else None
            rows.append({
                "劇本": sc + 1, "年(紀元前)": SCENARIO_YEARS[sc], "Id": r["id"], "姓名": p["name"],
                "勢力": names.get(r["faction"], r["faction"]), "君主": "○" if r["flags"] & 7 == 0 else "",
                "Flags": f"{r['flags']:X}", "年齢": p["born"] - SCENARIO_YEARS[sc],
                "体力": r["hp"], "上限": r["hp_max"], "戦闘": r["war"], "統率": r["command"], "用兵": r["tactics"],
                "経験": r["exp"], "外交": DIPLOMACY[r["diplomacy"] // 2] if r["diplomacy"] // 2 < len(DIPLOMACY) else r["diplomacy"],
                "軍": r["army"] + 1, "軍の将": persons[army["leader"]]["name"] if army and army["leader"] < len(persons) else "",
                "Unknown": r["unknown"],
            })
    return rows


def place_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        names = lords(rom, sc)
        for base, r in zip(rom.places(), rom.scenario_places(sc)):
            f = r["faction"]
            rows.append({"劇本": sc + 1, "Id": r["id"], "名": base["name"], "読み": base["reading"], "x": base["x"], "y": base["y"],
                         "勢力": names.get(f, "") if f != 0xFF else "", "金": r["gold"], "食料": r["food"],
                         "人口": r["population"], "支持": r["support"][f] if f < len(r["support"]) else "",
                         "疲弊": r["fatigue"], "防御": r["defense"], "農地": r["farm"]})
    return rows


def army_rows(rom: Rom) -> list[dict]:
    persons, places = rom.persons(), rom.places()
    rows = []
    for sc in range(SCENARIO_COUNT):
        names = lords(rom, sc)
        sp = rom.scenario_persons(sc)
        for a in rom.scenario_armies(sc):
            if a["leader"] >= len(persons):
                continue
            members = [persons[p["id"]]["name"] for p in sp if p["army"] == a["id"] and p["id"] != a["leader"] and p["flags"] & 7 == 1]
            rows.append({"劇本": sc + 1, "軍": a["id"] + 1, "勢力": names.get(a["faction"], a["faction"]),
                         "将": persons[a["leader"]]["name"], "所在": places[a["place"]]["name"] if a["place"] < len(places) else "",
                         "資金": a["gold"], "兵糧": a["food"], "兵士": a["soldiers"], "士気": a["morale"], "武装": a["arms"],
                         "付随": "、".join(members)})
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


def map_places(rom: Rom, path: str, cell: int = 16) -> None:
    """The 55 x 44 map cells: road cells (entry 1) and cells with a feature number (entry 2), places labelled."""
    roads, features = rom.entry(MAP_ROADS), rom.entry(MAP_FEATURES)
    im = Image.new("RGB", (MAP_W * cell, MAP_H * cell), (120, 150, 80))
    dr = ImageDraw.Draw(im)
    for i in range(MAP_W * MAP_H):
        x, y = i % MAP_W * cell, i // MAP_W * cell
        colour = (50, 90, 170) if roads[i] == 0 else (200, 170, 90) if features[i] else None
        if colour:
            dr.rectangle([x, y, x + cell - 1, y + cell - 1], fill=colour)
    try:
        font = ImageFont.truetype(LABEL_FONT, 12)
    except OSError:
        font = ImageFont.load_default(12)
    for p in rom.places():
        x, y = p["x"] * cell, p["y"] * cell
        dr.rectangle([x, y, x + cell - 1, y + cell - 1], outline="red", width=2)
        dr.text((x + cell + 2, y + cell // 2), f"{p['id']} {p['name']}", fill="white", anchor="lm", font=font,
                stroke_width=2, stroke_fill="black")
    im.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 項劉記 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "劇本人物": scenario_rows(rom), "地點": place_rows(rom), "軍隊": army_rows(rom)}
    for rows, fn in zip(sheets.values(), ("persons", "person_scenarios", "places", "armies")):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "kouryuuki.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p in rom.persons():
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["id"]), os.path.join(faces, f"{p['id']:02d}_{p['name']}.png"))
    for n in range(FACE_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"F{n:02d}.png"))
    map_places(rom, os.path.join(args.out, "map_places.png"))
    print(f"頭像 {len(rom.persons())} 人＋{FACE_COUNT} 張、地點圖 → {args.out}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
