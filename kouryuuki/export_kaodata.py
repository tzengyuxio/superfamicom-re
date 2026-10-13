#!/usr/bin/env python3
"""Export SFC 項劉記 as a kaodata dataset (kouryuuki-sfc, format kaodata/1).

Faces are portraits only: 97 faces of 40x48 (data entries 21-117), all with the one palette at FACE_PALETTE.
Person n uses face n.

Usage: .venv/bin/python kouryuuki/export_kaodata.py --out <dir> [--rom ROM]
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
    images, pixels = [], bytearray()
    portraits = []
    for n in range(FACE_COUNT):
        images.append([len(pixels), FACE_W * 8, FACE_H * 8])
        pixels.extend(rom.face_pixels(n))
        portraits.append({"img": n, "label": f"F{n:02d}"})
    characters = [{"id": p["id"], "name": p["name"], "reading": kaodata.hiragana(p["reading"]),
                   "face": {"portrait": p["id"]}} for p in rom.persons()]
    meta = {
        "format": kaodata.FORMAT,
        "id": "kouryuuki-sfc",
        "game": "KOURYUUKI",
        "platform": "SFC",
        "title": {"ja": "項劉記", "zh": "項劉記"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（全員共用）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(bgr555_rgb, rom.face_palette())]}],
        "blobs": ["portraits.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(pixels)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 kouryuuki-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Kouryuuki (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"kouryuuki-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
