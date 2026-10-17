#!/usr/bin/env python3
"""Export SFC スーパーロイヤルブラッド as a kaodata dataset (royal-sfc, format kaodata/1).

Faces are portraits only (no composite faces): 68 faces of 40x48, all with BG palette 1 of the strategy
screens (FACE_PALETTE). P00-P63 are the 64 characters (face = character id), P64-P67 the 4 advisors (group
相談役, name from the advisor menu: シドー ライアス フィラ アンガス). The game keeps no face code, so portraits
have no `code`. `reading` is the katakana name in hiragana.

Usage: .venv/bin/python royal/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import CHAR_COUNT, DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, Rom, bgr555_rgb


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    advisors = rom.advisor_names()
    images, pixels, portraits = [], bytearray(), []
    for n in range(FACE_COUNT):
        images.append([len(pixels), FACE_W * 8, FACE_H * 8])
        pixels.extend(rom.face_pixels(n))
        portraits.append({"img": n} if n < CHAR_COUNT else
                         {"img": n, "group": "相談役", "name": advisors[n - CHAR_COUNT]})
    characters = []
    for i in range(CHAR_COUNT):
        name = rom.char_name(i)["name"]
        characters.append({"id": i, "name": name, "reading": kaodata.hiragana(name), "face": {"portrait": i}})
    meta = {
        "format": kaodata.FORMAT,
        "id": "royal-sfc",
        "game": "ROYAL",
        "platform": "SFC",
        "title": {"ja": "スーパーロイヤルブラッド", "zh": "魔法皇冠"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（全員共用，BG 調色盤 1）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(bgr555_rgb, rom.face_palette())]}],
        "blobs": ["portraits.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(pixels)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 royal-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Super Royal Blood (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"royal-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
