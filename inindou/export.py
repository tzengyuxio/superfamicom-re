#!/usr/bin/env python3
"""匯出 SFC スーパー伊忍道 打倒信長 的人物、人物初始狀態、職業、武將、國、術、物品、敵人、敵特殊能力、地名、地點地圖、
職業圖示與字型。

Usage: .venv/bin/python inindou/export.py [--rom ROM] [--us-rom US_ROM] [--out DIR]

Writes files.csv, persons.csv, jobs.csv, generals.csv, provinces.csv, spells.csv, items.csv, enemies.csv,
enemy_skills.csv, places.csv, maps.csv, map_cells.csv (+ inindou.xlsx when openpyxl is installed), icons/ (the 16
job icons), maps/ (maps 0-37 drawn with the town tileset), font.png (the 1518 glyphs).
English names come from the US ROM (Inindo - Way of the Ninja), only matched to the Japanese records.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    DEFAULT_ROM,
    GLYPH_COUNT,
    ICON_COUNT,
    ICON_H,
    ICON_W,
    JOB_CODES,
    JOB_ICON,
    MAP_COUNT,
    START_VILLAGE,
    STATE_COUNT,
    STATE_FIELDS,
    TOWN_MAPS,
    US_ROM,
    Rom,
    us_enemy_names,
    us_person_names,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    im.save(path)


def hexs(b: bytes) -> str:
    return b.hex(" ")


def file_rows(rom: Rom) -> list[dict]:
    return [{"名稱": f["name"], "bank": f"{f['bank']:02X}", "位址": f"{f['addr']:04X}", "ROM 偏移": f"{f['offset']:06X}",
             "大小": f["size"]} for f in rom.files()]


def person_rows(rom: Rom, en: list[str]) -> list[dict]:
    jobs = rom.job_names()
    states = {s["person"]: s for s in rom.states()}
    rows = []
    for p in rom.persons():
        st = states.get(p["id"])
        row = {"id": p["id"], "姓名": p["name"], "英文名(美版ROM)": en[p["id"]] if en else "",
               "職業": jobs[p["job"]], "職業碼": f"{p['job']:02X}", "b12(未解)": p["b12"], "b13(推定所在地)": p["b13"],
               "b15(未解)": p["b15"], "初始狀態記錄": st["record"] if st else ""}
        for name in STATE_FIELDS:
            row[name] = st[name] if st else ""
        row["性別"] = ("女" if st["female"] else "男") if st else ""
        row["術遮罩(+18..21)"] = hexs(st["spell_masks"]) if st else ""
        row["裝備推定(+23..27)"] = " ".join(f"{x:02X}" for x in st["equipment"]) if st else ""
        row["狀態原始32B"] = hexs(st["raw"]) if st else ""
        rows.append(row)
    return rows


def job_rows(rom: Rom) -> list[dict]:
    persons = rom.persons()
    return [{"職業碼": f"{j['code']:02X}", "名稱": j["name"], "類別": j["group"], "圖示": j["icon"],
             "人數": sum(p["job"] == j["code"] for p in persons)} for j in rom.jobs()]


def general_rows(rom: Rom) -> list[dict]:
    gens, provs = rom.generals(), rom.provinces()
    where = {g: p for p, chain in rom.garrisons().items() for g in chain}
    values = rom.daimyo_values()
    rows = []
    for g in gens:
        p = where.get(g["id"])
        rows.append({"id": g["id"], "姓名": g["name"], "大名": "是" if g["id"] < 16 else "",
                     "所在國(初始)": provs[p]["name"] if p is not None else "",
                     "城主": "是" if p is not None and provs[p]["lord"] == g["id"] else "",
                     "所屬大名(初始)": gens[provs[p]["daimyo"]]["name"] if p is not None else "",
                     "值1(+15,未解)": g["v15"], "值2(+16,未解)": g["v16"],
                     "大名表值(0-4,未解)": values.get(g["id"], "") if g["id"] < 16 else ""})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    provs, gens, garrisons = rom.provinces(), rom.generals(), rom.garrisons()

    def gname(n: int) -> str:
        return gens[n]["name"] if n < len(gens) else f"{n:02X}"

    return [{"id": p["id"], "國名": p["name"], "表值(+5,未解)": p["value"],
             "相鄰": "、".join(provs[a]["name"] for a in p["adjacent"]),
             "大名": gname(p["daimyo"]), "城主": gname(p["lord"]), "金": p["金"], "米": p["米"], "兵": p["兵"],
             "+8(未解)": p["s8"], "+9(未解)": p["s9"], "+10..17(未解)": hexs(p["rest"]),
             "武將(城主起)": "、".join(gname(g) for g in garrisons[p["id"]])} for p in provs]


def spell_rows(rom: Rom) -> list[dict]:
    schools = ["忍術", "仙術", "妖術"]
    return [{"id": s["id"], "名稱": s["name"], "系統": schools[s["id"] // 14], "消費気力(推定)": s["気力"],
             "b8(未解)": s["b8"], "b9(未解)": s["b9"]} for s in rom.spells()]


def item_rows(rom: Rom) -> list[dict]:
    return [{"id": i["id"], "名稱": i["name"], "種類/效果(+0,未解)": f"{i['kind']:02X}", "價格": i["price"],
             "旗標(未解)": f"{i['flags']:04X}"} for i in rom.items()]


def enemy_rows(rom: Rom, en: dict) -> list[dict]:
    return [{"id": e["id"], "名稱": e["name"], "英文名(美版ROM，依資料比對)": e["en"],
             "資料23B(未解)": hexs(e["data"])} for e in rom.enemies(en)]


def enemy_skill_rows(rom: Rom) -> list[dict]:
    return [{"id": s["id"], "名稱": s["name"], "b7(未解)": s["b7"], "b8(未解)": s["b8"]} for s in rom.enemy_skills()]


def map_rows(rom: Rom) -> list[dict]:
    rows = []
    for m in range(MAP_COUNT):
        hd = rom.map_header(m)
        _, end = rom.map_cells(m)
        rows.append({"id": m, "寬": hd["w"], "高": hd["h"], "x(+2,推定入口)": hd["x"], "y(+3,推定入口)": hd["y"],
                     "ROM 偏移": f"{hd['offset']:06X}", "壓縮後大小": end - hd["offset"],
                     "圖塊": "町（遊戲畫面已驗證）" if m == START_VILLAGE else ("町（推定）" if m in TOWN_MAPS else "未解"),
                     "備註": "開新遊戲的村（伊賀）" if m == START_VILLAGE else ("空白 8x8" if m == 15 else "")})
    return rows


def cell_rows(rom: Rom) -> list[dict]:
    rows = []
    for m in range(MAP_COUNT):
        w = rom.map_header(m)["w"]
        cells, _ = rom.map_cells(m)
        rows += [{"地圖": m, "x": k % w, "y": k // w, "格碼": c} for k, c in enumerate(cells)]
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


def font_sheet(rom: Rom, path: str) -> None:
    cols = 32
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
    ap = argparse.ArgumentParser(description="匯出 SFC スーパー伊忍道 打倒信長 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--us-rom", default=US_ROM, help="美版 ROM，只用來對照英文名稱（找不到就略過）")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    have_us = os.path.exists(args.us_rom)
    en_persons = us_person_names(args.us_rom) if have_us else []
    en_enemies = us_enemy_names(args.us_rom) if have_us else {}

    sheets = {"檔案": file_rows(rom), "人物": person_rows(rom, en_persons), "職業": job_rows(rom),
              "武將": general_rows(rom), "國": province_rows(rom), "術": spell_rows(rom), "物品": item_rows(rom),
              "敵人": enemy_rows(rom, en_enemies), "敵特殊能力": enemy_skill_rows(rom),
              "地名": [{"id": n, "地名": s} for n, s in enumerate(rom.place_names())], "地圖": map_rows(rom),
              "地圖格": cell_rows(rom)}
    files = ("files", "persons", "jobs", "generals", "provinces", "spells", "items", "enemies", "enemy_skills",
             "places", "maps", "map_cells")
    for rows, fn in zip(sheets.values(), files):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "inindou.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    icons = os.path.join(args.out, "icons")
    os.makedirs(icons, exist_ok=True)
    jobs = rom.jobs()
    for n in range(ICON_COUNT):
        label = "・".join(j["name"] for k, j in enumerate(jobs) if JOB_ICON[k] == n)
        png(ICON_W * 8, ICON_H * 8, rom.icon_rgb(n), os.path.join(icons, f"{n:02d}_{label}.png"))
    maps = os.path.join(args.out, "maps")
    os.makedirs(maps, exist_ok=True)
    for m in TOWN_MAPS:
        w, h, rgb = rom.render_town_map(m)
        png(w, h, rgb, os.path.join(maps, f"map{m:02d}" + ("_start" if m == START_VILLAGE else "") + ".png"))
    font_sheet(rom, os.path.join(args.out, "font.png"))
    print(f"職業圖示 {ICON_COUNT} 張（{len(JOB_CODES)} 職業）、地點地圖 {len(TOWN_MAPS)} 張、字型 → {args.out}"
          f"（人物狀態 {STATE_COUNT} 筆）")


if __name__ == "__main__":
    main()
