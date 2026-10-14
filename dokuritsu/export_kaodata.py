#!/usr/bin/env python3
"""Export SFC 独立戦争 as a kaodata dataset (liberty-sfc, format kaodata/1).

All faces use one 16-colour palette (FACE_PALETTE). Portraits 0-173 are LZ entries 67-240; the face code of a
portrait is its number ("code" 0000-00AD). Composed faces (code bit 15 set, $C2:3E66 / $C2:3ADA): the code's
digits d0..d5 (2 bits each, from bit 10 down) select type d0 = variant and, for the parts the game draws in the
order 5, 1, 2, 3, 4, part variant d1..d5; each part writes whole 8x8 cells of the 40x48 face (rom.Rom.part_cells),
so every item is a 40x48 canvas with 255 outside the cells the part writes. The slots follow the drawing order.

Usage: .venv/bin/python dokuritsu/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import DEFAULT_ROM, FACE_H, FACE_W, PART_ORDER, PORTRAIT_COUNT, TYPE_COUNT, Rom, bgr555_rgb, decode_tile

CANVAS = (FACE_W * 8, FACE_H * 8)
PART_LABELS = {4: "下 2 列", 0: "上 4 列", 1: "第 3 列", 2: "第 4 列", 3: "第 5 列"}   # tile rows each part writes


def slot_id(p: int) -> str:
    return f"part{p}"


def part_image(rom: Rom, t: int, p: int, v: int) -> bytes:
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    src = rom.part_variant(t, p, v)
    for s, cell in rom.part_cells(t, p):
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, c in enumerate(decode_tile(src[32 * s:32 * s + 32])):
            out[(cy + i // 8) * w + cx + i % 8] = c
    return bytes(out)


def code_parts(code: int) -> tuple[int, list[int]]:
    d = [(code >> s) & 3 for s in (10, 8, 6, 4, 2, 0)]
    return d[0], [d[p + 1] for p in PART_ORDER]


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
    for t in range(TYPE_COUNT):
        parts = {slot_id(p): {"items": [add(part_image(rom, t, p, v)) for v in range(4)]} for p in PART_ORDER}
        variants.append({"id": str(t), "label": f"型 {t}", "parts": parts})

    portraits = [{"img": add(bytes(rom.face_pixels(n)), blob=1), "code": f"{n:04X}"} for n in range(PORTRAIT_COUNT)]

    characters = []
    for p in rom.persons():
        code = p["face"]
        ch = {"id": p["id"], "name": p["name"]}
        if code & 0x8000:
            t, parts = code_parts(code)
            ch["face"] = {"variant": t, "parts": parts, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (bgr555_rgb(c) for c in rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "liberty-sfc",
        "game": "LIBERTY",
        "platform": "SFC",
        "title": {"ja": "独立戦争 Liberty or Death", "zh": "獨立戰爭"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤", "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": slot_id(p), "label": PART_LABELS[p]} for p in PART_ORDER],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 liberty-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Dokuritsu Sensou - Liberty or Death (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"liberty-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
