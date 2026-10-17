#!/usr/bin/env python3
"""Export SFC ウイニングポスト2 as a kaodata dataset (winning2-sfc, format kaodata/1).

Pixels are `palette * 16 + colour`: the dataset palette is the game's 6 face palettes $C1:E52D + 32 p (96 colours;
rom.face_palette_number). There are no composed faces: the 208 portraits keep their face code (rom.face_code:
0-11 秘書 (6 secretaries, the second face from year 15), 12-133 騎手 (jockeys 0-60, the second face from age 35),
134-139 騎手 (women jockeys of slots 0x38 / 0x19 / 0x32 / 0x11 by year), 140-171 調教師 (trainers 0-19 and the
successors who take over their stables by year), 172-199 馬主, 200-207 其他).

Characters (face at the start of a game, year 0): trainers 1000-1019, jockeys 2000-2060 (jockeys 0-59 of the
new-game table and jockey 60, エドリー, the only jockey from ROM with a face of his own), owners 3000-3027 (owner
28, the player, has no face), secretaries 4000-4005.

With --rom Program '96 the dataset is winning2-96-sfc, a separate kaodata dataset (a standalone cartridge with its own
season: 174 faces kept at the same code, 8 moved, 26 dropped, 33 new): its 235 portraits and the same character ids by
its own records. The '96 original and Rev 1 give the same dataset.

Usage: .venv/bin/python winning2/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import (
    DEFAULT_ROM,
    FACE_H,
    FACE_KINDS,
    FACE_W,
    PALETTE_COUNT,
    Rom,
    bgr555_rgb,
    face_kind,
    face_palette_number,
    tiles_pixels,
)

CANVAS = (FACE_W * 8, FACE_H * 8)


def characters(rom: Rom) -> list[dict]:
    out = []
    for t in rom.trainers():
        out.append({"id": 1000 + t["index"], "name": t["surname"] + t["given"], "face": {"portrait": t["face"]}})
    for j in rom.jockeys()[:61]:
        out.append({"id": 2000 + j["index"], "name": j["surname"] + j["given"], "face": {"portrait": j["face"]}})
    for o in rom.owners()[:28]:
        out.append({"id": 3000 + o["index"], "name": o["surname"] + o["given"], "face": {"portrait": o["face"]}})
    for s in rom.secretaries():
        out.append({"id": 4000 + s["index"], "name": s["surname"] + s["given"], "face": {"portrait": s["face"]}})
    return out


def portrait_names(rom: Rom) -> dict[int, str]:
    names = {}
    for s in rom.secretaries():
        names[s["face"]] = s["surname"] + s["given"]
        names[s["face_later"]] = s["surname"] + s["given"] + "（15 年目以後）"
    return names


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob = [], bytearray()
    names = portrait_names(rom)
    portraits = []
    for code in range(rom.face_count):
        pal = face_palette_number(code)
        w, h = CANVAS
        images.append([len(blob), w, h])
        blob.extend(pal * 16 + v for v in tiles_pixels(rom.face_bytes(code)))
        p = {"img": code, "code": f"{code:02X}", "group": FACE_KINDS[face_kind(code)][3]}
        if code in names:
            p["name"] = names[code]
        portraits.append(p)
    colors = [f"#{r:02x}{g:02x}{b:02x}" for n in range(PALETTE_COUNT) for r, g, b in map(bgr555_rgb, rom.palette(n))]
    title, ds_id = {"ja": "ウイニングポスト2", "zh": "賽馬大亨2"}, "winning2-sfc"
    if rom.version == "program96":   # separate dataset: '96 drops and moves faces, so it can't merge into winning2-sfc
        title, ds_id = {"ja": "ウイニングポスト2 プログラム'96", "zh": "賽馬大亨2 Program'96"}, "winning2-96-sfc"
    meta = {
        "format": kaodata.FORMAT,
        "id": ds_id,
        "game": "WINNING2",
        "platform": "SFC",
        "title": title,
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 6 組調色盤 $C1:E52D + 32 × 組（色號＝組 × 16 ＋ 色）",
                      "colors": colors}],
        "blobs": ["portraits.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters(rom),
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 winning2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/ 的 zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"{meta['id']}: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
