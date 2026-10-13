#!/usr/bin/env python3
"""Export SFC 信長の野望・覇王伝 as a kaodata dataset (nobu5-sfc, format kaodata/1).

Pixels are colour numbers of the one face palette (16 colours, OBJ palette 7).
Composed faces ($C1:1835): one variant per face group (6). The game's build order becomes the slots: parts 0-4,
each taking variant (code >> 3p) & 7 (0-4) of the group's part pool and writing whole 8x8 cells of the 40x48
face given by the part's cell masks; every item is a 40x48 canvas with 255 outside the cells it writes.
Portraits are the 348 face LZ entries 93-440 (portrait n = entry 93 + n).
Characters are the 817 person ids; the face id is the person id.

Usage: .venv/bin/python haouden/export_kaodata.py --out <dir> [--rom ROM]
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
    FACE_ENTRY,
    FACE_GROUP_COUNT,
    FACE_H,
    FACE_PART_COUNT,
    FACE_PART_VARIANTS,
    FACE_W,
    Rom,
    bgr555_rgb,
    decode_tile,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
PORTRAIT_COUNT = 348
SLOTS = [(f"part{p}", f"部位{p + 1}") for p in range(FACE_PART_COUNT)]


def cells_image(cells: dict[int, bytes]) -> bytes:
    """40x48 image of the given {cell: tile bytes}, other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell, raw in cells.items():
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, v in enumerate(decode_tile(raw)):
            out[(cy + i // 8) * w + cx + i % 8] = v
    return bytes(out)


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for g in range(FACE_GROUP_COUNT):
        parts = {sid: {"items": [add(cells_image(rom.face_part_tiles(g, p, v))) for v in range(FACE_PART_VARIANTS)]}
                 for p, (sid, _) in enumerate(SLOTS)}
        variants.append({"id": str(g), "label": f"第 {g} 組", "parts": parts})

    portraits = []
    for n in range(PORTRAIT_COUNT):
        tiles = rom.entry(FACE_ENTRY + n)[:960]
        portraits.append({"img": add(bytes(rom.face_pixels(tiles=tiles)), blob=1)})

    characters = []
    for pid, m in rom.person_master().items():
        r = m["first"]
        ch = {"id": pid, "name": f"{r['surname']} {r['given']}"}
        s = rom.face_source(pid)
        if s[0] == "comp":
            ch["face"] = {"variant": s[1], "parts": [s[2] >> (3 * p) & 7 for p in range(FACE_PART_COUNT)],
                          "code": f"{s[2]:04X}"}
        else:
            ch["face"] = {"portrait": s[1]}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (bgr555_rgb(c) for c in rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "nobu5-sfc",
        "game": "NOBU5",
        "platform": "SFC",
        "title": {"ja": "信長の野望・覇王伝", "zh": "信長之野望・霸王傳"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（OBJ 調色盤 7）", "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label in SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 nobu5-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Nobunaga no Yabou - Haouden (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"nobu5-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
