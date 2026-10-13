#!/usr/bin/env python3
"""匯出 SFC 独立戦争 的人物、1775 年劇本、地點、州、陣營、HEX 戰場、頭像與大地圖。

Usage: .venv/bin/python dokuritsu/export.py [--rom ROM] [--out DIR]

Writes persons.csv, persons_1775.csv, locations.csv, locations_1775.csv, states.csv, sides.csv,
battle_maps.csv, battle_cells.csv (+ dokuritsu.xlsx when openpyxl is installed), faces/ (one PNG per person),
portraits/ (000-173), map_0_北部.png .. map_2_南部.png (land white, before the owner colours) and battle/
(the 53 HEX battle maps, 224 x 200).
"""
import argparse
import collections
import csv
import os

from PIL import Image
from rom import (
    BATTLE_H,
    BATTLE_W,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    FACTIONS,
    MAP_H,
    MAP_W,
    PORTRAIT_COUNT,
    REGIONS,
    RESERVE,
    STATS,
    TERRAIN_LOOKS,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([c or (0, 0, 0) for c in rgb])
    im.save(path)


def face_label(code: int) -> str:
    return f"組合 型{code >> 10 & 3}" if code & 0x8000 else f"專屬 {code:03d}"


def where(rom: Rom) -> dict[int, str]:
    """Person id -> where the 1775 lists put them."""
    locs = rom.locations()
    out = {}
    for s in rom.location_states():
        for k in s["persons"]:
            out[k] = f"{s['id'] + 1}:{locs[s['id']]['name']}"
    for side in rom.sides():
        for k in side["reserve_persons"]:
            out[k] = f"待機（{side['name']}）"
    return out


def person_rows(rom: Rom) -> list[dict]:
    return [{"Id": p["id"], "ROM_Offset": f"0x{p['offset']:05X}", "名": p["first"], "姓": p["last"],
             "頭文字": p["initial"], **{s: p[s] for s in STATS}, "種別(未解)": p["kind"],
             "Unknown29": p["unknown29"], "Unknown30": p["unknown30"], "頭像碼": f"{p['face']:04X}",
             "頭像": face_label(p["face"])} for p in rom.persons()]


def person_1775_rows(rom: Rom) -> list[dict]:
    persons, at = rom.persons(), where(rom)
    rows = []
    for s in rom.person_states():
        p = persons[s["id"]]
        rows.append({"Id": s["id"], "姓名": p["name"], "所在(列表)": at.get(s["id"], ""),
                     "地點欄(+2)": "待機" if s["location"] == RESERVE else s["location"] + 1,
                     "体力": s["体力"], "名声": s["名声"], "忠誠": s["忠誠"],
                     "所屬(推測)": FACTIONS.get(s["faction"], s["faction"]), "Unknown6低位": s["unknown6"],
                     "階級(推測)": s["rank"], "Flags7": f"0x{s['flags7']:02X}", "Unknown8_13": s["unknown8"],
                     "Raw": s["raw"].hex(" ")})
    return rows


def location_rows(rom: Rom) -> list[dict]:
    locs, states = rom.locations(), rom.states()
    return [{"Id": c["id"], "番號": c["no"], "名稱": c["name"], "地區": REGIONS[c["region"]],
             "州": states[c["state"]]["abbr"], "州名": states[c["state"]]["name"], "港(推測)": c["port"],
             "相鄰": "、".join(f"{n + 1}:{locs[n]['name']}" for n in c["neighbours"]),
             "Unknown0": c["unknown0"], "Flags1": f"0x{c['flags']:02X}", "ROM_Offset": f"0x{c['offset']:05X}"}
            for c in locs]


def location_1775_rows(rom: Rom) -> list[dict]:
    locs, persons = rom.locations(), rom.persons()
    return [{"Id": s["id"], "番號": s["id"] + 1, "名稱": locs[s["id"]]["name"], "Owner(未解)": s["owner"],
             "支持": s["支持"], "食糧": s["食糧"], "武器(推測)": s["武器"], "弾薬(推測)": s["弾薬"],
             "Unknown12": s["unknown12"], "人數": len(s["persons"]),
             "人物": "、".join(persons[k]["name"] for k in s["persons"])} for s in rom.location_states()]


def side_rows(rom: Rom) -> list[dict]:
    persons = rom.persons()
    return [{"Id": s["id"], "陣營": s["name"], "資金(推測)": s["funds"], "待機人數": len(s["reserve_persons"]),
             "待機人物": "、".join(persons[k]["name"] for k in s["reserve_persons"])} for s in rom.sides()]


def battle_rows(rom: Rom, maps: list[dict]) -> list[dict]:
    locs = rom.locations()
    rows = []
    for m in maps:
        cnt = collections.Counter(c["terrain"] for c in m["cells"])
        rows.append({"Id": m["id"], "地點": f"{m['id'] + 1}:{locs[m['id']]['name']}",
                     **{f"地形{t}{TERRAIN_LOOKS[t]}(推測)": cnt.get(t, 0) for t in range(11)},
                     "有疊加格": sum(c["overlay"] not in (0xFFFF, 0x8888) for c in m["cells"])})
    return rows


def cell_rows(maps: list[dict]) -> list[dict]:
    return [{"Map": m["id"], "X": c["x"], "Y": c["y"], "地形": c["terrain"], "外觀(推測)": TERRAIN_LOOKS[c["terrain"]], "Flags(未解)": f"0x{c['flags']:X}",
             "Byte1(未解)": f"0x{c['byte1']:02X}", "Overlay": f"{c['overlay']:04X}"}
            for m in maps for c in m["cells"]]


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
    ap = argparse.ArgumentParser(description="匯出 SFC 独立戦争 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    maps = [rom.battle_map(m) for m in range(len(rom.locations()))]

    sheets = {"人物": person_rows(rom), "人物1775": person_1775_rows(rom), "地點": location_rows(rom),
              "地點1775": location_1775_rows(rom), "州": [{"Id": s["id"], "略稱": s["abbr"], "名稱": s["name"]}
                                                         for s in rom.states()],
              "陣營": side_rows(rom), "戰場": battle_rows(rom, maps), "戰場格": cell_rows(maps)}
    names = ("persons", "persons_1775", "locations", "locations_1775", "states", "sides", "battle_maps",
             "battle_cells")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "dokuritsu.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for p in rom.persons():
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(p["face"]), os.path.join(faces, f"{p['id']:03d}_{p['name']}.png"))
    for n in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"{n:03d}.png"))
    for r, name in enumerate(REGIONS):
        png(MAP_W * 8, MAP_H * 8, rom.map_rgb(r), os.path.join(args.out, f"map_{r}_{name}.png"))
    bd = os.path.join(args.out, "battle")
    os.makedirs(bd, exist_ok=True)
    locs = rom.locations()
    for m in range(len(maps)):
        w, h, rgb = rom.battle_rgb(m)
        png(w, h, rgb, os.path.join(bd, f"{m:02d}_{locs[m]['name']}.png"))
    print(f"頭像 {len(rom.persons())} 人＋{PORTRAIT_COUNT} 張、大地圖 3 區、戰場 {len(maps)} 張"
          f"（{BATTLE_W} x {BATTLE_H} 格）→ {args.out}")


if __name__ == "__main__":
    main()
