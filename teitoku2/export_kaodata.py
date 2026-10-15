#!/usr/bin/env python3
"""Export SFC 提督の決断II as a kaodata dataset (tk2-sfc, format kaodata/1).

104 faces of 40x48 (LZ entries 753-856), drawn by the face routine ($D4:6DBC(x, y, f)) with face number f, which
each portrait carries as its "code". The game uses two 16-colour palettes (Rom.face_palette: Japanese / Allied,
rom.face_alt_palette), so the dataset palette is both (colour = palette * 16 + index). The 60 admirals (face i)
and 30 generals (face 60 + j) are the characters, with id = face number; faces 90-103 belong to nobody in the
tables and carry a group (rom.OTHER_FACES). Readings of the names are not in the ROM, so characters have none.
The event faces (LZ 488-531) are not exported: who they show is not known.

Usage: .venv/bin/python teitoku2/export_kaodata.py --out <dir> [--rom ROM]
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
    FACE_COUNT,
    FACE_H,
    FACE_W,
    GENERAL_FACE0,
    OTHER_FACES,
    Rom,
    bgr555_rgb,
    face_alt_palette,
    tiles_pixels,
)

PALETTE_FACES = (0, 30)  # a face of each palette


def characters(rom: Rom) -> list[dict]:
    img = rom.wram_image(0)
    out = [{"id": a["face"], "name": a["name"].replace(" ", ""), "face": {"portrait": a["face"]}}
           for a in rom.admirals(img)]
    out += [{"id": g["face"], "name": g["name"].replace(" ", ""), "face": {"portrait": g["face"]}}
            for g in rom.generals(img)]
    assert [c["id"] for c in out] == list(range(GENERAL_FACE0 + len(rom.generals(img))))
    return out


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, pixels, portraits = [], bytearray(), []
    for f in range(FACE_COUNT):
        images.append([len(pixels), FACE_W * 8, FACE_H * 8])
        base = 16 * face_alt_palette(f)
        pixels.extend(base + v for v in tiles_pixels(rom.face_tiles(f), FACE_W, FACE_H))
        portraits.append({"img": f, "code": f"{f:04X}", **({"group": OTHER_FACES[f]} if f in OTHER_FACES else {})})
    colors = [f"#{r:02x}{g:02x}{b:02x}" for f in PALETTE_FACES for r, g, b in map(bgr555_rgb, rom.face_palette(f))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "tk2-sfc",
        "game": "TK2",
        "platform": "SFC",
        "title": {"ja": "提督の決断II", "zh": "提督之決斷II"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 2 組調色盤（色號＝組 × 16 ＋ 色；0 日本、1 連合國）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters(rom),
    }
    return meta, [bytes(pixels)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 tk2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Teitoku no Ketsudan II (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"tk2-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits "
          f"({sum('group' in p for p in meta['portraits'])} with a group), {len(meta['images'])} images, "
          f"{len(meta['palettes'][0]['colors'])} colours")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
