#!/usr/bin/env python3
"""匯出 SFC 信長の野望・覇王伝 的人物、劇本人物、城、大名、各種名稱表、頭像與地圖。

Usage: .venv/bin/python haouden/export.py [--rom ROM] [--out DIR]

Writes persons.csv (person ids 0-819), person_scenarios.csv (3 scenarios, persons present at the start),
future_persons.csv (persons appearing later), castles.csv (110 castles x 3 scenarios), daimyo.csv,
provinces.csv, titles.csv, treasures.csv, princesses.csv, historic_battles.csv, terrains.csv,
battle_maps.csv (+ haouden.xlsx), faces/ (face ids 0-928 except 920-921), map.png (big map 1536 x 512),
battle/ (143 battle maps 640 x 376) and font.png (1808 glyphs).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BATTLE_COUNT,
    BATTLE_H,
    BATTLE_W,
    CASTLE_MAPS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    GLYPH_COUNT,
    HISTORIC_FIRST,
    MAP_H,
    MAP_W,
    SCENARIO_COUNT,
    SCENARIO_YEARS,
    STATS,
    TERRAIN_FIRST,
    Rom,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
# castle family -> maps it can pick ($C5:8330): 0x7E + random 0-2, 0x83 + random 0-1, 0x85 via the byte table
# $C5:F51A (133-136), 0x89 + an index not yet understood (137-142 assumed); 129-130 are not reached by this code.
TERRAIN_FAMILIES = {0x7E: (126, 128), 0x83: (131, 132), 0x85: (133, 136), 0x89: (137, 142)}


def png(w: int, h: int, rgb: list, path: str) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([c or (0, 0, 0) for c in rgb])
    im.save(path)


def face_label(rom: Rom, fid: int) -> str:
    s = rom.face_source(fid)
    return f"專屬 entry {93 + s[1]}" if s[0] == "entry" else f"組合 組{s[1]} {s[2]:04X}"


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for pid, m in rom.person_master().items():
        r = m["first"]
        sc, kind, _ = m["appear"][0]
        rows.append({"Id": pid, "姓": r["surname"], "名": r["given"], "其他名": "、".join(m["names"][1:]),
                     "生年": r["born"], **{s: r[s] for s in STATS},
                     "初登場": f"劇本{sc + 1}" + ("開始" if kind == "start" else f" {r['year']}年登場"),
                     "登場": "、".join(f"{s + 1}{'' if k == 'start' else '後'}" for s, k, _ in m["appear"]),
                     "頭像Id": pid, "頭像": face_label(rom, pid)})
    return rows


def scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        s = rom.scenario(sc)
        heads = {d["head"] for d in s["daimyo"]}
        castle_of = {}
        for c in s["castles"]:
            for p in c["members"]:
                castle_of[p["addr"]] = c
        year = SCENARIO_YEARS[sc]
        for p in s["persons"]:
            c = castle_of.get(p["addr"])
            d = next((x for x in s["daimyo"] if c and x["addr"] == c["daimyo"]), None)
            rank = "大名" if p["addr"] in heads else "城主" if c and c["lord"] == p["addr"] else "家臣" if c else ""
            rows.append({"劇本": sc + 1, "年": year, "Slot": p["slot"], "WRAM": f"$7E:{p['addr']:04X}", "Id": p["id"],
                         "姓": p["surname"], "名": p["given"], "生年": p["born"], "年齢": year - p["born"],
                         **{st: p[st] for st in STATS}, "気合": p["kiai"], "忠誠": p["loyalty"], "知行": p["fiefs"],
                         "身分": rank, "城": s["castles"][p["castle"]]["name"] if p["castle"] < 110 else p["castle"],
                         "大名家": d["head_person"]["surname"] if d else "",
                         "Unknown22": p["b22"], "Unknown23": p["b23"], "Unknown24": p["b24"],
                         "Unknown25": p["b25"], "Unknown27": p["b27"], "Unknown28": p["b28"],
                         "Unknown30hi": p["b30_hi"], "Unknown34_38": p["tail"]})
    return rows


def future_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        castles = rom.scenario_castles(sc)
        for f in rom.future_persons(sc):
            rows.append({"劇本": sc + 1, "No": f["no"], "登場年": f["year"], "Id": f["id"], "姓": f["surname"],
                         "名": f["given"], "生年": f["born"], **{st: f[st] for st in STATS},
                         "城": castles[f["castle"]]["name"] if f["castle"] < 110 else f["castle"],
                         "Unknown1": f["b1"], "Unknown2": f["b2"], "Unknown24": f["b24"], "Unknown25": f["b25"],
                         "Unknown28_29": f["tail"]})
    return rows


def castle_rows(rom: Rom) -> list[dict]:
    prov = rom.string_table("provinces")
    siege = rom.siege_types()
    cells = rom.castle_cells()
    rows = []
    for sc in range(SCENARIO_COUNT):
        s = rom.scenario(sc)
        d_by_addr = {d["addr"]: d for d in s["daimyo"]}
        for c in s["castles"]:
            d = d_by_addr.get(c["daimyo"])
            lord = c["members"][0] if c["members"] else None
            rows.append({"劇本": sc + 1, "Id": c["id"], "名": c["name"], "国": prov[c["province"]],
                         "大名家": d["head_person"]["surname"] + d["head_person"]["given"] if d else "",
                         "城主": lord["surname"] + lord["given"] if lord else "", "武將數": len(c["members"]),
                         "本城(推測)": c["main"], "規模": c["size"], "防": c["defense"], "貫": c["kan"],
                         "人": c["people"], "商": c["commerce"], "練": c["training"], "治": c["order"],
                         "兵": c["soldiers"], "銭": c["money"], "糧": c["food"], "鉄砲": c["guns"], "馬": c["horses"],
                         "地圖格x": cells[c["id"]][0], "地圖格y": cells[c["id"]][1],
                         "城戰場圖": c["id"], "無城戰場城類": f"0x{siege[c['id']]:02X}",
                         "Unknown0": c["head0"], "Unknown20": c["b20"], "Unknown35_37": c["tail"]})
    return rows


def daimyo_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        for d in rom.scenario(sc)["daimyo"]:
            h = d["head_person"]
            rows.append({"劇本": sc + 1, "Slot": d["slot"], "當主": h["surname"] + h["given"], "當主Id": h["id"],
                         "城數": len(d["castles"]), "城": "、".join(c["name"] for c in d["castles"]),
                         "貢献": d["contribution"], "家紋(推測)": d["crest"], "Unknown2": d["b2"],
                         "Unknown3_33": d["relations"], "Unknown35": d["b35"], "Unknown36": d["b36"],
                         "Unknown37": d["b37"]})
    return rows


def list_rows(names: list[str], col: str) -> list[dict]:
    return [{"Id": i, col: n} for i, n in enumerate(names)]


def historic_rows(rom: Rom) -> list[dict]:
    castles = rom.scenario_castles(0)
    return [{"Id": i, "合戦": n, "城": castles[c]["name"], "戰場圖": HISTORIC_FIRST + i}
            for i, (n, c) in enumerate(zip(rom.string_table("battles"), rom.historic_battle_castles()))]


def battle_rows(rom: Rom) -> list[dict]:
    castles = rom.scenario_castles(0)
    battles = rom.string_table("battles")
    family = rom.siege_types()
    rows = []
    for m in range(BATTLE_COUNT):
        if m < CASTLE_MAPS:
            kind, where = "城的戰場（圖上有城）", castles[m]["name"]
        elif m < HISTORIC_FIRST:
            kind, where = "特殊（$C1:024C / $C5:8925 在某條件下選用，條件未解）", ""
        elif m < TERRAIN_FIRST:
            kind, where = "合戦", battles[m - HISTORIC_FIRST]
        else:
            fam = next((f for f, (lo, hi) in TERRAIN_FAMILIES.items() if lo <= m <= hi), None)
            kind = "無城地形圖" + (f"（城類 0x{fam:02X}）" if fam else "（選用方式未解）")
            where = f"城類 0x{fam:02X} 的城 {family.count(fam)} 座" if fam else ""
        rows.append({"Id": m, "LZ entry": 466 + m, "種類": kind, "城／合戦": where})
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


def map_castles(rom: Rom, out: str) -> None:
    """map_castles.png: the big map at 2x with every castle's id and name at its icon cell."""
    im = Image.open(os.path.join(out, "map.png"))
    big = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    try:
        f = ImageFont.truetype(LABEL_FONT, 18)
    except OSError:
        f = ImageFont.load_default(18)
    for c, (x, y) in zip(rom.scenario_castles(0), rom.castle_cells()):
        dr.rectangle([x * 32, y * 32, x * 32 + 31, y * 32 + 31], outline="red", width=2)
        dr.text((x * 32 + 16, y * 32 + 34), f"{c['id']} {c['name']}", fill="white", anchor="mt", font=f,
                stroke_width=3, stroke_fill="black")
    big.save(os.path.join(out, "map_castles.png"))


def font_sheet(rom: Rom, path: str) -> None:
    cols = 64
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
    ap = argparse.ArgumentParser(description="匯出 SFC 信長の野望・覇王伝 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {
        "人物": person_rows(rom), "劇本人物": scenario_rows(rom), "後登場人物": future_rows(rom),
        "城": castle_rows(rom), "大名": daimyo_rows(rom),
        "国": list_rows(rom.string_table("provinces"), "国"), "官位": list_rows(rom.string_table("titles"), "官位"),
        "家宝": list_rows(rom.string_table("treasures"), "家宝"), "姫": list_rows(rom.string_table("princesses"), "名"),
        "合戦": historic_rows(rom), "地形": list_rows(rom.string_table("terrains"), "地形"), "戰場圖": battle_rows(rom),
    }
    names = ("persons", "person_scenarios", "future_persons", "castles", "daimyo", "provinces", "titles",
             "treasures", "princesses", "historic_battles", "terrains", "battle_maps")
    for rows, fn in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    write_xlsx(sheets, os.path.join(args.out, "haouden.xlsx"))

    names_by_id = {r["Id"]: r["姓"] + r["名"] for r in sheets["人物"]}
    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    for fid in rom.face_ids():
        tag = names_by_id.get(fid, "")
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(fid), os.path.join(faces, f"{fid:03d}{'_' + tag if tag else ''}.png"))
    png(MAP_W * 16, MAP_H * 16, rom.map_rgb(), os.path.join(args.out, "map.png"))
    map_castles(rom, args.out)
    battle = os.path.join(args.out, "battle")
    os.makedirs(battle, exist_ok=True)
    for r in sheets["戰場圖"]:
        tag = r["城／合戦"] or r["種類"][:2]
        png(BATTLE_W * 16, BATTLE_H * 16 + 8, rom.battle_rgb(r["Id"]), os.path.join(battle, f"{r['Id']:03d}_{tag}.png"))
    font_sheet(rom, os.path.join(args.out, "font.png"))
    print(f"頭像 {len(rom.face_ids())} 張、大地圖、戰場 {BATTLE_COUNT} 張、字型 → {args.out}")


if __name__ == "__main__":
    main()
