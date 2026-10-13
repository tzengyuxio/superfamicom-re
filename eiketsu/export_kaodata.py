#!/usr/bin/env python3
"""Export SFC 三國志英傑伝 as a kaodata dataset (eiketsu-sfc, format kaodata/1).

The game has no composed faces: faces 0-239 are portraits (48x48), all drawn with the one face palette
(CGRAM palette 3, FACE_PALETTE). Each of the 384 persons points at a face (name record +14); several persons
share a face.

Usage: .venv/bin/python eiketsu/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, Rom, bgr555_rgb


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    w, h = FACE_W * 8, FACE_H * 8
    images, blob = [], bytearray()
    portraits = []
    for n in range(FACE_COUNT):
        px = bytes(rom.face_pixels(n))
        assert len(px) == w * h
        images.append([len(blob), w, h])
        blob.extend(px)
        portraits.append({"img": n, "label": f"{n:03d}"})
    characters = [{"id": p["id"], "name": p["name"], "reading": kaodata.hiragana(p["reading"]),
                   "face": {"portrait": p["face"]}} for p in rom.persons()]
    meta = {
        "format": kaodata.FORMAT,
        "id": "eiketsu-sfc",
        "game": "EIKETSU",
        "platform": "SFC",
        "title": {"ja": "三國志英傑伝", "zh": "三國志英傑傳"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（全員共用，CGRAM 第 3 組）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(bgr555_rgb, rom.face_palette())]}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 eiketsu-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Sangokushi Eiketsuden (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"eiketsu-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
