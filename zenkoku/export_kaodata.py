#!/usr/bin/env python3
"""Export SFC スーパー信長の野望・全国版 as a kaodata dataset (nobu2-sfc, format kaodata/1).

Pixels are colour numbers 0-15 of the one face palette (ROM 0x7F796, OBJ palette 5 of the province screen;
verify_persons.py checks it). There are no composite faces: the 73 portraits are LZ streams 120-192 and the
game picks one with byte 6 of the daimyo record (the person id, written as the portrait "code"). Characters are
the 68 person ids 0-67 with their kanji names from the scenario tables; portraits 68-72 are women (姫) that no
daimyo record uses. The ROM has no readings.

Usage: .venv/bin/python zenkoku/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_H, FACE_W, PERSON_COUNT, PORTRAIT_COUNT, Rom

CANVAS = (FACE_W * 8, FACE_H * 8)


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob = [], bytearray()
    portraits = []
    for n in range(PORTRAIT_COUNT):
        px = rom.face_pixels(n)
        assert len(px) == CANVAS[0] * CANVAS[1]
        images.append([len(blob), *CANVAS])
        blob.extend(px)
        pt = {"img": len(images) - 1, "code": f"{n:02X}"}
        if n >= PERSON_COUNT:
            pt["group"] = "姫"
        portraits.append(pt)

    characters = [{"id": p["id"], "name": p["name"], "face": {"portrait": p["id"]}} for p in rom.persons()]
    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in rom.face_palette()]
    meta = {
        "format": kaodata.FORMAT,
        "id": "nobu2-sfc",
        "game": "NOBU2",
        "platform": "SFC",
        "title": {"ja": "スーパー信長の野望・全国版", "zh": "超級信長之野望・全國版"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（OBJ 調色盤 5）", "colors": colors}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(blob)]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 nobu2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Super Nobunaga no Yabou - Zenkoku Ban (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    print(f"nobu2-sfc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits "
          f"({sum('group' in p for p in meta['portraits'])} 姫), {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
