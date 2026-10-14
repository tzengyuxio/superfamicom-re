#!/usr/bin/env python3
"""匯出 SFC エアーマネージメントII 航空王をめざせ 的都市、國家、地區、劇本、世界事件、機種、製造商、關聯事業、頭像、地圖與字型。

Usage: .venv/bin/python airmanage2/export.py [--rom ROM] [--out DIR] [--scale N]

Writes cities.csv, scenario_cities.csv, countries.csv, areas.csv, events.csv, aircraft.csv, makers.csv,
businesses.csv, init_tables.csv (unsolved bytes), files.csv (+ airmanage2.xlsx), faces/ + faces.png,
world_map.png, world_map_cities.png, area_maps/area_N.png (+ cities), font.png.
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    AREA_COUNT,
    CITY_COUNT,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    SCENARIO_COUNT,
    WORLD_LAND_ROW,
    Rom,
    half_to_full,
)

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
GROUPS = {"SECRET": "秘書", "STAFF": "職員", "MAKER": "廠商", "MAYOR": "國家代表"}


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


def city_rows(rom: Rom) -> list[dict]:
    areas = rom.areas()
    return [{"番號": c["index"], "都市": c["name_full"], "都市(半形)": c["name"], "地區": areas[c["area"]]["name"],
             "國家(劇本1)": half_to_full(c["country_name"]), "可為本社": "○" if c["home"] else "",
             "預設航空公司": c["airline"], "地區地圖X": c["area_x"], "地區地圖Y": c["area_y"],
             "世界地圖X": c["world_x"], "世界地圖Y": c["world_y"]} for c in rom.cities()]


def scenario_rows(rom: Rom) -> list[dict]:
    cities, countries = rom.cities(), rom.countries()
    out = []
    for s in range(SCENARIO_COUNT):
        rec, rec2 = rom.scenario_cities(s)
        for i in range(CITY_COUNT):
            r = rec[4 * i:4 * i + 4]
            out.append({"劇本": s + 1, "番號": i, "都市": cities[i]["name_full"],
                        "國家": half_to_full(countries[r[0]]["name"]), "國家番號": r[0],
                        "[未解]值1": r[1], "[未解]值2": r[2], "[未解]值3": r[3], "[未解]第二記錄": rec2[2 * i]})
    return out


def country_rows(rom: Rom) -> list[dict]:
    t = {s: rom.init_tables(s)[0x2E21] for s in range(SCENARIO_COUNT)}
    e815 = rom.data[rom.b5(0xE815):rom.b5(0xE815) + 55]
    out = []
    for c in rom.countries():
        row = {"番號": c["index"], "國家": half_to_full(c["name"]), "國家(半形)": c["name"]}
        for s in range(SCENARIO_COUNT):
            row[f"[未解]$2E21 劇本{s + 1}"] = t[s][c["index"]]
        row["[未解]$05:E815"] = e815[c["index"]] if c["index"] < len(e815) else ""
        out.append(row)
    return out


def area_rows(rom: Rom) -> list[dict]:
    cities = rom.cities()
    return [{"番號": a["index"], "地區": a["name"], "本社都市": " ".join(
        cities[i]["name_full"] for i in range(a["hq_first"], a["hq_first"] + a["hq_count"])),
        "其他都市": " ".join(cities[i]["name_full"] for i in range(a["other_first"], a["other_first"] + a["other_count"])),
        "本社都市遮罩": f"{a['hq_mask']:08X}", "秘書/職員調色盤": "26-29" if a["index"] in (0, 4, 5) else
        {1: "8-11", 2: "12-15", 6: "12-15", 3: "16-19"}[a["index"]],
        "國家代表調色盤": rom.mayor_face(a["hq_first"])[2]} for a in rom.areas()]


def event_rows(rom: Rom) -> list[dict]:
    cities, countries = rom.cities(), rom.countries()
    out = []
    for e in rom.events():
        row = {"番號": e["index"], "年": e["year"], "[未解]季": e["quarter"], "[未解]訊息": e["message"],
               "種類": e["type"]}
        if e["type"] == 0:
            row.update({"對象": cities[e["target"]]["name_full"], "內容": "國家改為 "
                        + half_to_full(countries[e["value"]]["name"])})
        else:
            row.update({"對象": half_to_full(countries[e["target"]]["name"]),
                        "內容": f"[未解]$2E21 值改為 {e['value']}"})
        out.append(row)
    return out


def aircraft_rows(rom: Rom) -> list[dict]:
    makers = rom.makers()
    return [{"番號": p["index"], "機種": p["name"], "メーカー": half_to_full(makers[p["maker"]]["name"]),
             "座席数": p["seats"], "航続距離(km)": p["range_km"], "基準価格(万$)": p["price"], "燃費": p["fuel"],
             "整備性": p["maintenance"], "生産開始": p["first_year"], "[推測]生産終了": p["last_year"] or "",
             "[未解]旗標": p["flags"]} for p in rom.aircraft()]


def maker_rows(rom: Rom) -> list[dict]:
    planes = rom.aircraft()
    return [{"番號": m["index"], "メーカー": half_to_full(m["name"]), "メーカー(半形)": m["name"],
             "頭像": m["face_image"], "調色盤": m["face_palette"], "[未解]$05:EEBC": m["eebc"],
             "機種": " ".join(p["name"] for p in planes if p["maker"] == m["index"])} for m in rom.makers()]


def business_rows(rom: Rom) -> list[dict]:
    names = rom.strings(0xDAD3, 15)
    return [{"番號": i, "關聯事業": half_to_full(n), "關聯事業(半形)": n} for i, n in enumerate(names)]


def init_rows(rom: Rom) -> list[dict]:
    out = []
    for addr, b in rom.init_tables().items():
        out.append({"WRAM": f"${addr:04X}", "大小": len(b), "[未解]內容": b.hex(" ")})
    return out


def file_rows(rom: Rom) -> list[dict]:
    out = []
    for f in rom.files():
        try:
            n = len(rom.lz(f["name"]))
        except (ValueError, IndexError):
            n = ""
        out.append({"番號": f["index"], "名稱": f["name"], "bank": f"${f['bank']:02X}", "位址": f"${f['addr']:04X}",
                    "檔案偏移": f"0x{f['offset']:05X}", "大小": f["size"], "KOEI LZ 解壓後": n})
    return out


def save_rgb(px: list[list[tuple]], path: str, scale: int) -> Image.Image:
    im = Image.new("RGB", (len(px[0]), len(px)))
    im.putdata([c for row in px for c in row])
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(path)
    return im


def export_faces(rom: Rom, out: str, scale: int) -> None:
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    faces = rom.faces()
    w, h = FACE_W * 8, FACE_H * 8
    sheet = Image.new("RGB", (8 * (w + 4) * scale, ((len(faces) + 7) // 8) * (h + 16) * scale), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for n, f in enumerate(faces):
        name = f"{f['file']}_{f['image']:02d}" + (f"_maker{f['maker']:02d}" if "maker" in f else "")
        im = save_rgb(rom.face_rgb(f["kind"], f["image"], f["palette"]), os.path.join(out, "faces", name + ".png"),
                      scale)
        x, y = (n % 8) * (w + 4) * scale, (n // 8) * (h + 16) * scale
        sheet.paste(im, (x, y))
        label = half_to_full(f["maker_name"]) if "maker" in f else f"{GROUPS[f['file']]}{f['image']}"
        size = 11 * scale
        while size > 6 and draw.textlength(label, font=font(size)) > (w + 3) * scale:
            size -= 1
        draw.text((x, y + h * scale + 1), label, fill=(255, 255, 255), font=font(size))
    sheet.save(os.path.join(out, "faces.png"))


def export_maps(rom: Rom, out: str, scale: int) -> None:
    world = save_rgb(rom.world_map(), os.path.join(out, "world_map.png"), 1)
    big = world.resize((world.width * 3, world.height * 3), Image.NEAREST)
    d = ImageDraw.Draw(big)
    for c in rom.cities():
        x, y = 3 * c["world_x"], 3 * c["world_y"]
        d.ellipse((x - 4, y - 4, x + 4, y + 4), outline=(255, 0, 0), width=2)
        d.text((x + 5, y - 7), c["name_full"], fill=(255, 255, 255), font=font(10))
    big.save(os.path.join(out, "world_map_cities.png"))
    os.makedirs(os.path.join(out, "area_maps"), exist_ok=True)
    for a in range(AREA_COUNT):
        im = save_rgb(rom.area_map(a), os.path.join(out, "area_maps", f"area_{a}.png"), 1)
        big = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
        d = ImageDraw.Draw(big)
        for c in rom.cities():
            if c["area"] == a:
                x, y = 3 * (c["area_x"] + 4), 3 * (c["area_y"] + 4)
                d.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(255, 0, 0) if c["home"] else (255, 255, 0), width=2)
                d.text((x + 8, y - 8), c["name_full"], fill=(255, 255, 255), font=font(14))
        big.save(os.path.join(out, "area_maps", f"area_{a}_cities.png"))


def export_font(rom: Rom, out: str) -> None:
    chars = rom.font_chars()
    cols = 32
    im = Image.new("L", (cols * 18, ((len(chars) + cols - 1) // cols) * 18), 255)
    for n, (_, code) in enumerate(chars):
        g = rom.glyph_pixels(code)
        x0, y0 = (n % cols) * 18, (n // cols) * 18
        for y, row in enumerate(g):
            for x, v in enumerate(row):
                if v:
                    im.putpixel((x0 + x, y0 + y), 0)
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(out, "font.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2, help="頭像放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    sheets = {"cities": city_rows(rom), "scenario_cities": scenario_rows(rom), "countries": country_rows(rom),
              "areas": area_rows(rom), "events": event_rows(rom), "aircraft": aircraft_rows(rom),
              "makers": maker_rows(rom), "businesses": business_rows(rom), "init_tables": init_rows(rom),
              "files": file_rows(rom)}
    for name, rows in sheets.items():
        write_csv(rows, os.path.join(args.out, name + ".csv"))
    write_xlsx(sheets, os.path.join(args.out, "airmanage2.xlsx"))
    export_faces(rom, args.out, args.scale)
    export_maps(rom, args.out, args.scale)
    export_font(rom, args.out)
    for name, rows in sheets.items():
        print(f"{name}.csv: {len(rows)} rows")
    print(f"faces: {len(rom.faces())}; world map 256x{len(rom.world_map())} (land rows from {WORLD_LAND_ROW}); "
          f"{AREA_COUNT} area maps; font {len(rom.font_chars())} glyphs -> {args.out}")


if __name__ == "__main__":
    main()
