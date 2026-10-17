#!/usr/bin/env python3
"""匯出 SFC トップマネジメントII 的都道府縣、人口、本社候補、劇本、公司、產品、難度、產業、新聞、頭像與日本地圖。

Usage: .venv/bin/python topman2/export.py [--rom ROM] [--out DIR] [--scale N]

Writes prefectures.csv, hq_pairs.csv, scenarios.csv, companies.csv, products.csv, levels.csv, industries.csv,
news.csv, faces.csv, files.csv (+ topman2.xlsx), faces/ + faces.png, japan_large.png (+ _prefectures with the
$01:CBAD positions), japan_small.png, prefecture_map.png (JAPANS with the $01:CD25 runs of every prefecture filled).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import DEFAULT_ROM, FACE_H, FACE_W, POP_YEAR_LIMITS, Rom

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"  # any font with kanji; PIL default if missing
POP_PERIODS = ["~1979", "1980~1984", "1985~1989", "1990~1994", "1995~"]
assert len(POP_PERIODS) == len(POP_YEAR_LIMITS) + 1


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


def prefecture_rows(rom: Rom) -> list[dict]:
    out = []
    for p in rom.prefectures():
        row = {"番號": p["code"], "名稱": p["name"]}
        for period, v in zip(POP_PERIODS, p["population"]):
            row[f"人口(萬人) 開始年 {period}"] = v
        row.update({"JAPANL 畫面 x ($CBAD)": p["xy_cbad"][0], "JAPANL 畫面 y ($CBAD)": p["xy_cbad"][1],
                    "$CC69 x (未解)": p["map_xy"][0], "$CC69 y (未解)": p["map_xy"][1],
                    "JAPANS 填色段數": len(p["spans"]), "填色方向": "縱" if p["spans"][0][3] else "橫"})
        out.append(row)
    return out


def hq_pair_rows(rom: Rom) -> list[dict]:
    names = [p["name"] for p in rom.prefectures()]
    return [{"r1": i, "r2=0 本社": names[a - 1], "r2=1 本社": names[b - 1], "據點(兩縣)": f"{names[a - 1]}、{names[b - 1]}"}
            for i, (a, b) in enumerate(rom.hq_pairs())]


def scenario_rows(rom: Rom) -> list[dict]:
    out = []
    for s in rom.scenarios():
        free_len = {6: "開始年 +4", 7: "開始年 +9"}.get(s["index"], "")
        out.append({"番號": s["index"], "模式": s["mode"], "名稱": s["name"],
                    "開始年": s["start_year"] or "自選 (1978 起，R 鍵 +1)", "結束年": s["end_year"] or free_len,
                    "說明": s["description"].replace("\n", "")})
    return out


def face_rows(rom: Rom) -> list[dict]:
    return [{"file": f["file"], "frame": f["frame"], "group": f["group"], "label": f["label"], "person": f["person"],
             "expression": f["expression"]} for f in rom.faces()]


def file_rows(rom: Rom) -> list[dict]:
    out = []
    for f in rom.files():
        n = rom.lz_size(f)
        out.append({"番號": f["index"], "名稱": f["name"], "bank": f"${f['bank']:02X}", "位址": f"${f['addr']:04X}",
                    "檔案偏移": f"0x{f['offset']:05X}", "大小": f["size"], "KOEI LZ 解壓後": n if n else ""})
    return out


def save_rgb(px: list[list[tuple]], path: str, scale: int) -> Image.Image:
    im = Image.new("RGB", (len(px[0]), len(px)))
    im.putdata([c for row in px for c in row])
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(path)
    return im


def face_name(f: dict) -> str:
    return f"{f['file']}_{f['frame']:02d}"


def export_faces(rom: Rom, out: str, scale: int) -> None:
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    faces = rom.faces()
    w, h = FACE_W * 8, FACE_H * 8
    cols = 12
    sheet = Image.new("RGB", (cols * (w + 4) * scale, ((len(faces) + cols - 1) // cols) * (h + 16) * scale),
                      (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for n, f in enumerate(faces):
        im = save_rgb(rom.face_rgb(f["file"], f["frame"]), os.path.join(out, "faces", face_name(f) + ".png"), scale)
        x, y = (n % cols) * (w + 4) * scale, (n // cols) * (h + 16) * scale
        sheet.paste(im, (x, y))
        label = f"{f['file']} {f['frame']}"
        size = 9 * scale
        while size > 6 and draw.textlength(label, font=font(size)) > (w + 3) * scale:
            size -= 1
        draw.text((x, y + h * scale + 1), label, fill=(255, 255, 255), font=font(size))
    sheet.save(os.path.join(out, "faces.png"))


def export_maps(rom: Rom, out: str) -> None:
    small = save_rgb(rom.japan_small(), os.path.join(out, "japan_small.png"), 1)
    s = 4
    big = small.resize((small.width * s, small.height * s), Image.NEAREST)
    d = ImageDraw.Draw(big)
    for p in rom.prefectures():
        hue = (p["index"] * 47) % 360
        col = tuple(int(c) for c in Image.new("HSV", (1, 1), (hue * 255 // 360, 160, 230)).convert("RGB").getpixel((0, 0)))
        for x, y, n, vertical in p["spans"]:
            w, h = (1, n) if vertical else (n, 1)
            d.rectangle((s * x, s * y, s * (x + w) - 1, s * (y + h) - 1), fill=col)
    for p in rom.prefectures():
        pts = [(x + (0 if v else k), y + (k if v else 0)) for x, y, n, v in p["spans"] for k in range(n)]
        cx, cy = sum(a for a, _ in pts) / len(pts), sum(b for _, b in pts) / len(pts)
        d.text((s * cx, s * cy), str(p["code"]), fill=(0, 0, 0), font=font(14), anchor="mm")
    big.save(os.path.join(out, "prefecture_map.png"))
    # JAPANL as the home / office selection screen shows it (cell (2, 3)), with the $01:CBAD positions + 8
    large = Image.new("RGB", (256, 224))
    large.paste(save_rgb(rom.japan_large(), os.path.join(out, "japan_large.png"), 1), (16, 24))
    large = large.resize((256 * 3, 224 * 3), Image.NEAREST)
    d = ImageDraw.Draw(large)
    for p in rom.prefectures():
        x, y = (3 * (v + 8) for v in p["xy_cbad"])
        d.ellipse((x - 5, y - 5, x + 5, y + 5), outline=(255, 0, 0), width=2)
        d.text((x + 7, y - 8), p["name"], fill=(255, 255, 0), font=font(13))
    large.save(os.path.join(out, "japan_large_prefectures.png"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2, help="頭像放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    sheets = {
        "prefectures": prefecture_rows(rom),
        "hq_pairs": hq_pair_rows(rom),
        "scenarios": scenario_rows(rom),
        "companies": [{"番號": c["index"], "預設名稱": c["name"]} for c in rom.companies()],
        "products": [{"番號": p["index"], "略稱": p["short"], "名稱": p["name"], "日文": p["name_ja"]}
                     for p in rom.products()],
        "levels": [{"番號": i, "名稱": v} for i, v in enumerate(rom.levels())],
        "industries": [{"番號": i, "名稱": v} for i, v in enumerate(rom.industries())],
        "news": [{"番號": i, "標題": v.replace("\n", " ")} for i, v in enumerate(rom.news())],
        "faces": face_rows(rom),
        "files": file_rows(rom),
    }
    for name, rows in sheets.items():
        write_csv(rows, os.path.join(args.out, name + ".csv"))
    write_xlsx(sheets, os.path.join(args.out, "topman2.xlsx"))
    export_faces(rom, args.out, args.scale)
    export_maps(rom, args.out)
    for name, rows in sheets.items():
        print(f"{name}.csv: {len(rows)} rows")
    print(f"faces: {len(rom.faces())}; maps: japan_large(_prefectures), japan_small, prefecture_map -> {args.out}")


if __name__ == "__main__":
    main()
