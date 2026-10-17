#!/usr/bin/env python3
"""Export SFC リーディングカンパニー as a kaodata dataset (leading-sfc, format kaodata/1).

The game has no named characters: its 44 faces are 会長 (PRESIDEN 4), 社長 (COMPTOP 12), 秘書 (SECRETAR 12)
and 4 managers per department (MANLABO 開発, MANFACTO 生産, MANBUSID 営業, MANACCOU 経理), the same grouping as
the PC-98 / X68000 datasets (leading-pc98, leading-x68). Each portrait is the 40 x 48 base face (the 3 animation
strips are not exported); all use the one palette file KAO. Portraits carry their group, no name or code.

Usage: .venv/bin/python leading/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_H, FACE_W, Rom, bgr555_rgb


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, pixels, portraits = [], bytearray(), []
    for f in rom.faces():
        images.append([len(pixels), FACE_W * 8, FACE_H * 8])
        pixels.extend(v for row in rom.face_pixels(f["kind"], f["image"]) for v in row)
        portraits.append({"img": len(images) - 1, "group": f["group"]})
    meta = {
        "format": kaodata.FORMAT,
        "id": "leading-sfc",
        "game": "LEADING",
        "platform": "SFC",
        "title": {"ja": "リーディングカンパニー", "zh": "龍頭企業"},  # zh: 超任終極聖經
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤 KAO（全員共用）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(bgr555_rgb, rom.face_palette())]}],
        "blobs": ["portraits.bin"],
        "images": images,
        "portraits": portraits,
        "characters": [],
    }
    return meta, [bytes(pixels)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 leading-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Leading Company (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"leading-sfc: {len(meta['portraits'])} portraits, {len(meta['images'])} images, "
          f"{len(meta['characters'])} characters")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
