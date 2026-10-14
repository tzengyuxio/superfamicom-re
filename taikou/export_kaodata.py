#!/usr/bin/env python3
"""Export SFC 太閤立志伝 as a kaodata dataset (taikoh-sfc, format kaodata/1).

Pixels are colour numbers of the one face palette (16 colours, OBJ palette 1 at ROM 0xD8FC9).
Composed faces ($CD:35CC, face code bit 15 set): one variant per face type (12, code bits 8-11). The game's build
order becomes the slots: parts 0-3, part k taking variant (code >> (6 - 2k)) & 3 of the type's part pool and
writing whole 8x8 cells of the 32x40 face given by the part's cell mask; every item is a 32x40 canvas with 255
outside the cells it writes.
Portraits are the 258 face LZ entries 81-338 (portrait n = face code n = entry 81 + n).
Characters are the 716 name table entries (character id = name id, as the person records refer to them); the
face is the entry's face code.

Usage: .venv/bin/python taikou/export_kaodata.py --out <dir> [--rom ROM]
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
    COMP_SLOTS,
    COMP_TYPES,
    COMP_VARIANTS,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    PORTRAIT_COUNT,
    Rom,
    bgr555_rgb,
    composite_parts,
    decode_tile,
    is_composite,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [(f"part{k}", f"部位{k + 1}") for k in range(COMP_SLOTS)]


def cells_image(cells: dict[int, bytes]) -> bytes:
    """32x40 image of the given {cell: tile bytes}, other cells transparent."""
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
    for t in range(COMP_TYPES):
        parts = {sid: {"items": [add(cells_image(rom.composite_part(t, k, v))) for v in range(COMP_VARIANTS)]}
                 for k, (sid, _) in enumerate(SLOTS)}
        variants.append({"id": str(t), "label": f"第 {t} 型", "parts": parts})

    portraits = [{"img": add(bytes(rom.face_pixels(n)), blob=1), "code": f"{n:04X}"} for n in range(PORTRAIT_COUNT)]

    characters = []
    for n in rom.names():
        code = n["face"]
        ch = {"id": n["id"], "name": f"{n['surname']} {n['given']}".strip()}
        if is_composite(code):
            t, parts = composite_parts(code)
            ch["face"] = {"variant": t, "parts": parts, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (bgr555_rgb(c) for c in rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "taikoh-sfc",
        "game": "TAIKOH",
        "platform": "SFC",
        "title": {"ja": "太閤立志伝", "zh": "太閤立志傳"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（OBJ 調色盤 1）", "colors": colors}],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 taikoh-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Taikou Risshiden (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"taikoh-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
