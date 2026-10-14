#!/usr/bin/env python3
"""Export SFC 大航海時代II as a kaodata dataset (koukai2-sfc, format kaodata/1).

Pixels are `palette * 16 + colour`; the dataset palettes are the portrait palette (0) and the two palettes of the
composed faces (1: packs 0, 1, 3-6; 2: pack 2). Portraits 0-127 use palette 0.
Composed faces ($C1:3B22, code bit 15): one variant per pack (7; pack bits 12-14, 7 = 6). The game's build order
becomes the slots: upper face (bits 9-11, cells 0-19), lower face (bits 0-2, cells 20-29, pack 1 also cell 15),
part A (bits 3-5) and part B (bits 6-8), each one of the pack's 8 faces restricted to the cells the routine copies
(rom.Rom.part_cells); every item is a 40x48 canvas with 255 outside its cells.

Usage: .venv/bin/python daikoukai2/export_kaodata.py --out <dir> [--rom ROM]
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
    FACE_BYTES,
    FACE_H,
    FACE_W,
    PACK_COUNT,
    PACK_PALETTE,
    PORTRAIT_COUNT,
    PORTRAIT_PALETTE,
    Rom,
    bgr555_rgb,
    decode_tile,
    le16,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [("upper", "上半臉"), ("lower", "下半臉"), ("a", "部件A（第4-5列）"), ("b", "部件B（第3列）")]


def palette_number(code: int) -> int:
    if not code & 0x8000:
        return 0
    return 2 if Rom.pack_of(code) == 2 else 1


def cells_image(face: bytes, cells: list[int], palette: int) -> bytes:
    """40x48 image of the given cells of a 960-byte face, other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell in cells:
        px = decode_tile(face[32 * cell:32 * cell + 32])
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, v in enumerate(px):
            out[(cy + i // 8) * w + cx + i % 8] = palette * 16 + v
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
    for t in range(PACK_COUNT):
        pack, cells = rom.pack_tiles(t), rom.part_cells(t)
        pal = 2 if t == 2 else 1
        parts = {sid: {"items": [add(cells_image(pack[FACE_BYTES * k:FACE_BYTES * (k + 1)], cells[sid], pal))
                                 for k in range(8)]} for sid, _ in SLOTS}
        variants.append({"id": str(t), "label": f"第 {t} 包", "parts": parts})

    portraits = [{"img": add(bytes(v for v in rom.face_pixels(n)), blob=1), "code": f"{n:04X}"}
                 for n in range(PORTRAIT_COUNT)]

    characters = []
    for p in rom.persons():
        code = p["face"]
        ch = {"id": str(p["id"]), "name": p["name"], "reading": kaodata.hiragana(p["name"])}
        if code & 0x8000:
            ch["face"] = {"variant": rom.pack_of(code), "parts": rom.face_parts(code), "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for at in (PORTRAIT_PALETTE, PACK_PALETTE, PACK_PALETTE + 32)
              for r, g, b in (bgr555_rgb(le16(rom.data, at + 2 * i)) for i in range(16))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "koukai2-sfc",
        "game": "KOUKAI2",
        "platform": "SFC",
        "title": {"ja": "大航海時代II", "zh": "大航海時代II"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 3 組調色盤（0 專屬頭像、1 組合臉、2 組合臉第 2 包；色號＝組 × 16 ＋ 色）",
                      "colors": colors}],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 koukai2-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Daikoukai Jidai II (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"koukai2-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
