#!/usr/bin/env python3
"""匯出 SFC スーパーロイヤルブラッド 的人物、家、領地、部隊、戰場、頭像與地圖。

Usage: .venv/bin/python royal/export.py [--rom ROM] [--out DIR] [--scale N]

Writes characters.csv (4 scenarios, present characters), persons.csv (64 name records), houses.csv,
provinces.csv, units.csv, battle_maps.csv (+ royal.xlsx when openpyxl is installed), faces/ (64 characters),
advisors/ (4), map.png and battle_maps/ (30). English names come from Gemfire (USA) when that ROM is present.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    BATTLE_H,
    BATTLE_W,
    CHAR_COUNT,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    MAP_H,
    MAP_W,
    PROVINCE_COUNT,
    SCENARIO_COUNT,
    SCENARIO_NAMES,
    STATUS,
    TERRAIN,
    US_ROM,
    Rom,
    UsNames,
)

HERE = os.path.dirname(os.path.abspath(__file__))
EN = "英語名(Gemfire)"


def png(rgb: list, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def person_rows(rom: Rom, us: UsNames) -> list[dict]:
    rows = []
    for i in range(CHAR_COUNT):
        n = rom.char_name(i)
        rows.append({"編號": i, "姓名": n["name"], EN: us.char(i), "年齢基數": n["age_base"],
                     "姓名表+13(未知)": f"{n['name_unknown']:02X}", "頭像": f"F{i:02d}",
                     "登場劇本": " ".join(str(s + 1) for s in range(SCENARIO_COUNT)
                                      if any(c["id"] == i for c in rom.characters(s)))})
    return rows


def character_rows(rom: Rom, us: UsNames) -> list[dict]:
    pnames = [rom.province_info(p)["name"] for p in range(PROVINCE_COUNT)]
    rows = []
    for s in range(SCENARIO_COUNT):
        for c in rom.characters(s):
            rows.append({
                "劇本": s + 1, "編號": c["id"], "姓名": c["name"], EN: us.char(c["id"]), "年齢": c["age"],
                "知力": c["int"], "武力": c["war"], "魅力": c["charm"],
                "所在領地": f"{c['province'] + 1}:{pnames[c['province']]}", "家": rom.house_name(c["house"]),
                "身分": STATUS.get(c["status"], str(c["status"])),
                "一族(推定)": "" if c["blood"] is None else rom.house_name(c["blood"]),
                "当主值(未知)": c["lord_value"], "頭像": f"F{c['id']:02d}",
            })
    return rows


def house_rows(rom: Rom, us: UsNames) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        provs = rom.provinces(s)
        playable = rom.selectable_lords(s)
        for h in rom.houses(s):
            owned = [p["id"] + 1 for p in provs if p["owner"] == h["id"]]
            rows.append({"劇本": s + 1, "劇本名": SCENARIO_NAMES[s], "編號": h["id"], "家": h["name"],
                         EN: us.house(h["id"]), "当主": rom.char_name(h["lord"])["name"],
                         "玩家可選": "○" if h["lord"] in playable else "", "領地數": len(owned),
                         "領地": " ".join(map(str, owned)), "旗標位元(未知)": f"{h['bits']:02X}"})
    return rows


def province_rows(rom: Rom, us: UsNames) -> list[dict]:
    units = rom.units()
    rows = []
    for s in range(SCENARIO_COUNT):
        chars = rom.characters(s)
        for p in rom.provinces(s):
            members = [c["name"] for c in chars if c["province"] == p["id"]]
            rows.append({
                "劇本": s + 1, "編號": p["id"] + 1, "領地": p["name"], EN: us.province(p["id"]),
                "支配家": rom.house_name(p["owner"]) if p["owner"] is not None else "",
                "金": p["gold"], "食料": p["food"], "兵": p["men"], "開発(推定)": p["land"], "作物(推定)": p["crops"],
                "民忠(推定)": p["loyalty"],
                "部隊槽(推定傭兵候補；種類:兵力/末位元組)": " ".join(
                    f"{units[u['type']]['name']}:{u['hp']}/{u['level']}" for u in p["units"]),
                "人物數": len(members), "人物": " ".join(members),
                "相鄰": " ".join(str(n + 1) for n in p["neighbours"]),
                "家標記格": f"{p['marker'][0]},{p['marker'][1]}",
            })
    return rows


def unit_rows(rom: Rom, us: UsNames) -> list[dict]:
    return [{"編號": u["id"], "名稱": u["name"], EN: us.unit(u["id"]), "+11(攻擊?)": u["a"], "+12(防禦?)": u["b"],
             "+13(初期兵力)": u["hp"], "+15": u["c"], "+16": u["d"], "+17(類別位元)": f"{u['kind']:02X}",
             "原值(+10..17)": u["raw"]} for u in rom.units()]


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in range(PROVINCE_COUNT):
        g = rom.battle_grid(p)
        rows.append({"編號": p + 1, "領地": rom.province_info(p)["name"], "寬": BATTLE_W, "高": BATTLE_H,
                     "地形(高4位元，每列以/分隔)": "/".join(
                         "".join(f"{v >> 4:x}" for v in g[r * BATTLE_W:(r + 1) * BATTLE_W]) for r in range(BATTLE_H)),
                     "地形種類": " ".join(TERRAIN[t] for t in sorted({v >> 4 for v in g}))})
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
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
        ws.freeze_panes = "A2"
    wb.save(path)
    print(f"已匯出 → {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC スーパーロイヤルブラッド 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--us-rom", default=US_ROM, help="Gemfire (USA)，只用來取英語名")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom, us = Rom(args.rom), UsNames(args.us_rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom, us), "劇本人物": character_rows(rom, us), "家": house_rows(rom, us),
              "領地": province_rows(rom, us), "部隊": unit_rows(rom, us), "戰場": battle_rows(rom)}
    for rows, name in zip(sheets.values(), ["persons", "characters", "houses", "provinces", "units", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "royal.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    w, h = FACE_W * 8, FACE_H * 8
    d = os.path.join(args.out, "faces")
    os.makedirs(d, exist_ok=True)
    for i in range(CHAR_COUNT):
        png(rom.face_rgb(i), w, h, os.path.join(d, f"F{i:02d}_{rom.char_name(i)['name']}.png"), args.scale)
    d = os.path.join(args.out, "advisors")
    os.makedirs(d, exist_ok=True)
    for k, name in enumerate(rom.advisor_names()):
        png(rom.face_rgb(CHAR_COUNT + k), w, h, os.path.join(d, f"F{CHAR_COUNT + k}_{name}.png"), args.scale)
    png(rom.map_rgb(), MAP_W * 8, MAP_H * 8, os.path.join(args.out, "map.png"), args.scale)
    d = os.path.join(args.out, "battle_maps")
    os.makedirs(d, exist_ok=True)
    for p in range(PROVINCE_COUNT):
        png(rom.battle_rgb(p), BATTLE_W * 16, BATTLE_H * 16,
            os.path.join(d, f"{p + 1:02d}_{rom.province_info(p)['name']}.png"), args.scale)
    print(f"頭像 人物 {CHAR_COUNT}＋相談役 4、大地圖 {MAP_W * 8}×{MAP_H * 8}、戰場 {PROVINCE_COUNT} 張 → {args.out}")


if __name__ == "__main__":
    main()
