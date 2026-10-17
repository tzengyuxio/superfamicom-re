#!/usr/bin/env python3
"""Export SFC スーパー麻雀大会 as a kaodata dataset (mahjong-sfc, format kaodata/1).

Each of the 21 opponents has one face stream of seven images (rom.Rom.face_tiles): faces 0-5 (40x40: normal,
two talking mouth frames, laughing, crying, surprised) and a 56x56 angry image. They are portraits 7i .. 7i + 6
of opponent i; the character's face is portrait 7i and the other six are its expressions, in stream order, with
labels. The game draws the faces with one of two 16-colour palettes ($01:8925 selects one per opponent), so the
dataset palette is both of them (32 colours) and a pixel is `16 * select + colour`. Colour 0 is drawn opaque, as
in the game's face windows.

Usage: .venv/bin/python mahjong/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_COUNT, FACE_PAL_SELECT, PERSON_COUNT, Rom, bgr555_rgb

IMAGES = FACE_COUNT + 1
LABELS = ["普通", "說話 1", "說話 2", "笑", "哭", "驚", "怒"]


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, pixels, portraits = [], bytearray(), []
    for i in range(PERSON_COUNT):
        base = 16 * rom.data[FACE_PAL_SELECT + i]
        for k in range(IMAGES):
            w, h = rom.face_size(k)
            images.append([len(pixels), 8 * w, 8 * h])
            pixels.extend(base + v for v in rom.face_pixels(i, k))
            portraits.append({"img": len(images) - 1})
    characters = []
    for p in rom.persons():
        n = IMAGES * p["id"]
        characters.append({"id": p["id"], "name": p["name"], "reading": kaodata.hiragana(p["reading"].replace(" ", "")),
                           "face": {"portrait": n, "label": LABELS[0]},
                           "expressions": [{"portrait": n + k, "label": LABELS[k]} for k in range(1, IMAGES)]})
    colors = [f"#{r:02x}{g:02x}{b:02x}" for k in (0, 1) for r, g, b in map(bgr555_rgb, rom.face_palette(k))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "mahjong-sfc",
        "game": "MAHJONG",
        "platform": "SFC",
        "title": {"ja": "スーパー麻雀大会", "zh": "超級麻雀大會"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤 $01:9384 與 $01:93A4（色號＝第幾組 × 16 ＋ 色）",
                      "colors": colors}],
        "blobs": ["portraits.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(pixels)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 mahjong-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Super Mahjong Taikai (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"mahjong-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
