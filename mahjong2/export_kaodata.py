#!/usr/bin/env python3
"""Export SFC 麻雀大会II as a kaodata dataset (mahjong2-sfc, format kaodata/1).

Each of the 26 opponents has one face stream of nine images (rom.Rom.face_tiles): 0-6 and 8 are 40x40 (normal, two
talking mouth frames, laughing, troubled, crying, displeased; 8 surprised), 7 is 56x56 (angry). They are portraits
9(p-1) .. 9(p-1) + 8 of opponent p; the character's face is the first and the other eight are its expressions, in
stream order, with labels. The game draws the faces with the palettes $02:8000 + 32k, k = 4-8 ($01:CCB1 per opponent;
$01:CCCB for the 56x56 image), so the dataset palette is those five (80 colours) and a pixel is `16 * (k - 4) +
colour`. Colour 0 is drawn opaque, as in the game's face windows.

Usage: .venv/bin/python mahjong2/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_IMAGES, FACE_LABELS, PERSONS, Rom, bgr555_rgb

IMAGES = len(FACE_IMAGES)
LABELS = FACE_LABELS
PALETTE_FIRST, PALETTE_COUNT = 4, 5


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, pixels, portraits = [], bytearray(), []
    for p in PERSONS:
        for k in range(IMAGES):
            base = 16 * (rom.image_palette(p, k) - PALETTE_FIRST)
            w, h = rom.face_size(k)
            images.append([len(pixels), 8 * w, 8 * h])
            pixels.extend(base + v for v in rom.face_pixels(p, k))
            portraits.append({"img": len(images) - 1})
    characters = []
    for c in rom.persons():
        n = IMAGES * (c["id"] - 1)
        characters.append({"id": c["id"], "name": c["name"], "reading": kaodata.hiragana(c["reading"].replace(" ", "")),
                           "face": {"portrait": n, "label": LABELS[0]},
                           "expressions": [{"portrait": n + k, "label": LABELS[k]} for k in range(1, IMAGES)]})
    colors = [f"#{r:02x}{g:02x}{b:02x}" for k in range(PALETTE_FIRST, PALETTE_FIRST + PALETTE_COUNT)
              for r, g, b in map(bgr555_rgb, rom.palette(k))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "mahjong2-sfc",
        "game": "MAHJONG2",
        "platform": "SFC",
        "title": {"ja": "麻雀大会II", "zh": "麻雀大會II"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤 $02:8080–$02:811F 第 4–8 組（色號＝(組 − 4) × 16 ＋ 色）",
                      "colors": colors}],
        "blobs": ["portraits.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(pixels)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 mahjong2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Mahjong Taikai II (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"mahjong2-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
