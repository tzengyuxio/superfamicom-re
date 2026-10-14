#!/usr/bin/env python3
"""Export SFC エアーマネージメント 大空に賭ける as a kaodata dataset (air-sfc, format kaodata/1).

The game has no named characters: its 33 faces are 8 aides (MANAGER), 20 negotiation partners (PERSON)
and 5 aircraft-maker representatives (MAKER), so the dataset has portraits only. Pixels are
`palette * 16 + colour` over the 12 palettes of PAL_M (192 colours); each portrait uses the palette the game
pairs with it (rom.Rom.default_palette, checked by verify_faces.py). Portrait order: MANAGER 0-7, PERSON 0-19,
MAKER 0-4. The game draws faces from a (kind, image, palette) descriptor, not from a single face code, so the
portraits carry no "code". Each portrait has a group (its kind, in Chinese) so the face browser lists it; the
maker faces are named after their maker (MAKER image m is maker m's descriptor).

Usage: .venv/bin/python airmanage/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_H, FACE_W, Rom, bgr555_rgb

CANVAS = (FACE_W * 8, FACE_H * 8)
GROUPS = {"MANAGER": "部下", "PERSON": "交涉對象", "MAKER": "廠商"}
PALETTE_COUNT = 12


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob, portraits = [], bytearray(), []
    # Half-width katakana to full width; the game writes the long vowel of ﾜ-ﾙﾄﾞﾘ-ｽ as "-"
    makers = {m["face_image"]: unicodedata.normalize("NFKC", m["name"]).replace("-", "ー") for m in rom.makers()}
    for f in rom.faces():
        px = bytes(f["palette"] * 16 + v for row in rom.face_pixels(f["kind"], f["image"]) for v in row)
        assert len(px) == CANVAS[0] * CANVAS[1]
        images.append([len(blob), *CANVAS])
        blob.extend(px)
        portrait = {"img": len(images) - 1, "group": GROUPS[f["file"]]}
        if f["file"] == "MAKER":
            portrait["name"] = makers[f["image"]]
        portraits.append(portrait)
    colors = [f"#{r:02x}{g:02x}{b:02x}" for p in range(PALETTE_COUNT)
              for r, g, b in (bgr555_rgb(c) for c in rom.face_palette(p))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "air-sfc",
        "game": "AIR",
        "platform": "SFC",
        "title": {"ja": "エアーマネージメント 大空に賭ける", "zh": "航空霸業"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 12 組調色盤（色號＝組 × 16 ＋ 色）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": [],
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 air-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Air Management - Oozora ni Kakeru (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"air-sfc: {len(meta['portraits'])} portraits, {len(meta['images'])} images, "
          f"{len(meta['characters'])} characters")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
