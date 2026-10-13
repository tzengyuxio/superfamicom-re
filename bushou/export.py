#!/usr/bin/env python3
"""匯出 SFC スーパー信長の野望・武将風雲録 的武將、國、大名、茶器、戰場、頭像與地圖。

Usage: .venv/bin/python bushou/export.py [--rom ROM] [--out DIR] [--scale N]

Writes scenarios.csv, generals.csv (both scenarios: start, renamed and later generals), provinces.csv
(per scenario), province_list.csv (names and neighbours), daimyo.csv, tea.csv, battle_maps.csv, files.csv
(+ bushou.xlsx), faces/ (one PNG per distinct character), portraits/ (F000-F179), mob_parts/, map.png,
battle_maps/field/ (the 48 field maps as the game draws them), battle_maps/castle/ (terrain values of the 49
castle maps, schematic: the castle screen is not decoded) and font.png (the 868 glyphs).
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from rom import (
    BATTLE_H,
    CASTLE_COUNT,
    CASTLE_W,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    FIELD_COUNT,
    FIELD_TERRAIN,
    FIELD_W,
    GLYPH_COUNT,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    Rom,
    decode_face_code,
    is_composite,
)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import parts_sheet

LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing


def png(w: int, h: int, rgb: list, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata(rgb)
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def font(size: int):
    try:
        return ImageFont.truetype(LABEL_FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def face_label(code: int) -> str:
    if not is_composite(code):
        return f"F{code:03d}"
    head, pages = decode_face_code(code)
    return f"組合 頭{head} " + "".join(str(p) for p in pages)


def all_generals(rom: Rom) -> list[dict]:
    """Start, renamed and later generals of every scenario, with resolved names."""
    pnames = rom.province_names()
    out = []
    for s in range(SCENARIO_COUNT):
        info = rom.scenario_info(s)
        daimyo = {d["index"]: d["name"] for d in rom.daimyos(s)}
        for g in rom.generals(s):
            out.append({"scenario": s + 1, "kind": "開局", **g, "province_name": pnames[g["province"]],
                        "daimyo_name": daimyo.get(g["daimyo"], "")})
        for g in rom.renamed(s):
            out.append({"scenario": s + 1, "kind": "改名", **g, "age": info["year"] - g["birth"]})
        for g in rom.later_generals(s):
            out.append({"scenario": s + 1, "kind": "登場", **g,
                        "province_name": "" if g["province"] is None else pnames[g["province"]]})
    return out


def scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        info = rom.scenario_info(s)
        rows.append({"劇本": s + 1, "名稱": info["name"], "年": info["year"], "月": info["month"],
                     "開局武將": len(rom.generals(s)), "改名": len(rom.renamed(s)),
                     "登場武將": len(rom.later_generals(s)), "大名": len(rom.daimyos(s)),
                     "有主國": sum(1 for p in rom.provinces(s) if p["owner"] is not None)})
    return rows


def general_rows(rom: Rom) -> list[dict]:
    rows = []
    for g in all_generals(rom):
        rows.append({
            "劇本": g["scenario"], "種別": g["kind"], "編號": g["index"], "姓名": g["name"], "姓": g["family"],
            "名": g["given"], "生年": g["birth"], "年齢": g.get("age", ""), "登場年": g.get("appear", ""),
            "政治": g.get("politics", ""), "戦闘": g.get("war", ""), "教養": g.get("culture", ""),
            "魅力": g["charm"], "野望": g["ambition"], "忠誠": g.get("loyalty", ""),
            "所在國": g.get("province_name", ""), "大名": g.get("daimyo_name", ""),
            "旗標(未解)": f"{g['flags']:02X}" if "flags" in g else "",
            "未知b8／登場b2": g.get("b8", g.get("b2", "")), "登場b7(未解)": g.get("b7", ""),
            "姓名b16(未解)": g["name_b16"], "頭像碼": f"{g['face_code']:04X}", "頭像": face_label(g["face_code"]),
            "姓名表偏移": f"0x{g['name_offset']:05X}"})
    return rows


def province_list_rows(rom: Rom) -> list[dict]:
    names = rom.province_names()
    return [{"編號": p, "國": names[p],
             "相鄰": " ".join(names[n] for n, _ in rom.province_neighbours(p)),
             "相鄰高2bits(未解)": " ".join(str(h) for _, h in rom.province_neighbours(p))}
            for p in range(len(names))]


def province_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        daimyo = {d["index"]: d["name"] for d in rom.daimyos(s)}
        gens = rom.generals(s)
        for p in rom.provinces(s):
            rows.append({
                "劇本": s + 1, "編號": p["index"], "國": p["name"],
                "大名": daimyo.get(p["owner"], "") if p["owner"] is not None else "",
                "金": p["gold"], "米": p["rice"], "石高": p["kokudaka"], "治水": p["flood"], "町": p["town"],
                "文化": p["culture"], "技術": p["tech"], "民忠": p["people_loyalty"], "城": p["castle"],
                "兵": p["soldiers"], "鉄砲": p["guns"], "訓練": p["training"], "兵忠": p["soldier_loyalty"],
                "武將數": len(p["generals"]), "武將": " ".join(gens[g]["name"] for g in p["generals"]),
                "指標2(未解)": f"{p['ptr2']:04X}", "未知19-21(載入時改寫)": p["raw19_21"],
                "未知30-31": p["raw30_31"]})
    return rows


def daimyo_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        ds = rom.daimyos(s)
        name = {d["index"]: d["name"] for d in ds}
        for d in ds:
            rows.append({"劇本": s + 1, "編號": d["index"], "大名": d["name"],
                         "同盟": " ".join(name.get(x, str(x)) for x in d["b2_4"]),
                         "關係表(未解，每家 4 bits)": "".join(f"{v:X}" for v in d["relations"]),
                         "b29(未解)": d["b29"], "b30(未解)": d["b30"], "b31(載入時改寫)": d["b31"]})
    return rows


def tea_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        gens = rom.generals(s)
        for t in rom.tea(s):
            rows.append({"劇本": s + 1, "編號": t["index"], "茶器": t["name"], "值(未解)": t["value"],
                         "持有者": "" if t["owner"] is None else gens[t["owner"]]["name"]})
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    pnames, (fnames, cnames) = rom.province_names(), rom.battle_names()
    rows = []
    for castle, count, w, names in ((False, FIELD_COUNT, FIELD_W, fnames), (True, CASTLE_COUNT, CASTLE_W, cnames)):
        for n in range(count):
            terrain = rom.battle_terrain(castle, n)
            row = {"種類": "城" if castle else "野戰", "編號": n, "國": pnames[24 if n == 48 else n],
                   "戰場名(推定)": names[n], "寬": w, "高": BATTLE_H,
                   "地形(每列以/分隔)": "/".join(terrain[r * w:(r + 1) * w].hex() for r in range(BATTLE_H))}
            if castle:
                layer = rom.castle_layer(n)
                row["第二層(未解)"] = "/".join(layer[r * w:(r + 1) * w].hex() for r in range(BATTLE_H))
            rows.append(row)
    return rows


def file_rows(rom: Rom) -> list[dict]:
    return [{"檔名": f["name"], "bank": f"{f['bank']:02X}", "位址": f"{f['addr']:04X}",
             "ROM偏移": f"0x{f['offset']:05X}", "大小": f["size"]} for f in rom.files()]


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
        ws.freeze_panes = "A2"
    wb.save(path)


CASTLE_COLOURS = [(40, 40, 40), (200, 60, 60), (120, 120, 120), (220, 140, 60), (90, 160, 90), (230, 200, 80),
                  (160, 100, 200), (110, 190, 80), (170, 150, 90), (40, 120, 40), (255, 255, 255), (255, 255, 255),
                  (130, 110, 100), (60, 110, 220), (255, 255, 255), (255, 255, 255)]


def castle_schematic(rom: Rom, n: int, path: str) -> None:
    """Hex grid of the castle map's terrain values (not game graphics: the castle screen is not decoded)."""
    terrain, cell = rom.battle_terrain(True, n), 24
    im = Image.new("RGB", (CASTLE_W * cell + 8, BATTLE_H * cell + cell // 2 + 8), (255, 255, 255))
    d, f = ImageDraw.Draw(im), font(10)
    for i, t in enumerate(terrain):
        r, c = divmod(i, CASTLE_W)
        x, y = 4 + c * cell, 4 + r * cell + (c & 1) * cell // 2
        d.rectangle([x, y, x + cell - 2, y + cell - 2], fill=CASTLE_COLOURS[t & 15])
        d.text((x + cell // 2, y + cell // 2), f"{t:X}", fill=(0, 0, 0), anchor="mm", font=f)
    im.save(path)


def font_sheet(rom: Rom, path: str) -> None:
    cols, cw, ch = 32, 36, 18
    rows = (GLYPH_COUNT + cols - 1) // cols
    im = Image.new("RGB", (cols * cw, rows * ch), (255, 255, 255))
    px, d, f = im.load(), ImageDraw.Draw(im), font(14)
    for g in range(GLYPH_COUNT):
        gx, gy = g % cols * cw, g // cols * ch
        for y, row in enumerate(rom.glyph(g)):
            for x, v in enumerate(row):
                if v:
                    px[gx + x, gy + y] = (0, 0, 0)
        d.text((gx + 17, gy + 1), rom.charset[g], fill=(0, 0, 200), font=f)
    im.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 SFC 武将風雲録 武將／國／大名／茶器／戰場／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"劇本": scenario_rows(rom), "武將": general_rows(rom), "國": province_rows(rom),
              "國名與相鄰": province_list_rows(rom), "大名": daimyo_rows(rom), "茶器": tea_rows(rom),
              "戰場": battle_rows(rom), "檔案表": file_rows(rom)}
    names = ["scenarios", "generals", "provinces", "province_list", "daimyo", "tea", "battle_maps", "files"]
    for rows, name in zip(sheets.values(), names):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    write_xlsx(sheets, os.path.join(args.out, "bushou.xlsx"))

    import export_kaodata  # imports all_generals from this module: load it after this module is complete

    chars = export_kaodata.distinct_characters(rom)
    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    for c in chars:
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(c["face_code"]), os.path.join(faces, f"{c['id']:03d}_{c['name']}.png"),
            args.scale)
    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for n in range(PORTRAIT_COUNT):
        png(FACE_W * 8, FACE_H * 8, rom.face_rgb(n), os.path.join(portraits, f"F{n:03d}.png"), args.scale)
    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)

    w, h, rgb = rom.map_rgb()
    png(w, h, rgb, os.path.join(args.out, "map.png"), args.scale)

    pnames, (fnames, cnames) = rom.province_names(), rom.battle_names()
    fdir, cdir = os.path.join(args.out, "battle_maps", "field"), os.path.join(args.out, "battle_maps", "castle")
    os.makedirs(fdir, exist_ok=True)
    os.makedirs(cdir, exist_ok=True)
    for n in range(FIELD_COUNT):
        w, h, rgb = rom.battle_rgb(rom.battle_terrain(False, n))
        png(w, h, rgb, os.path.join(fdir, f"{n:02d}_{pnames[n]}_{fnames[n]}.png"), args.scale)
    for n in range(CASTLE_COUNT):
        castle_schematic(rom, n, os.path.join(cdir, f"{n:02d}_{pnames[24 if n == 48 else n]}_{cnames[n]}.png"))
    font_sheet(rom, os.path.join(args.out, "font.png"))

    print(f"已匯出 {len(sheets['武將'])} 筆武將、{len(sheets['國'])} 筆國、{len(sheets['大名'])} 筆大名、"
          f"{len(sheets['茶器'])} 筆茶器、{len(sheets['戰場'])} 張戰場 → {args.out}")
    print(f"頭像 {len(chars)} 人＋專屬 {PORTRAIT_COUNT} 張；野戰地圖 {FIELD_COUNT} 張（地形 {len(FIELD_TERRAIN)} 種）；"
          f"城地圖 {CASTLE_COUNT} 張（僅地形示意）；字型 {GLYPH_COUNT} 字")


if __name__ == "__main__":
    main()
