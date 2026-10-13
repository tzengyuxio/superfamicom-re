#!/usr/bin/env python3
"""Export SFC 三國志III as a kaodata dataset (san3-sfc, format kaodata/1).

All faces use the one palette at FACE_PALETTE. Plain faces 1-307 (data entries 154-460) are portraits 0-306.
Composite faces (face word bit 15) are 13 types x 5 parts ($C1:6477): each type is a variant, each part a
slot whose items are its stored variants (6, 2, 4, 4, 4), every item a 40x48 canvas with 255 outside the
part's cells. A character's face is {variant: type, parts: [variant of part 0-4]}.

Usage: .venv/bin/python san3/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import kaodata
from rom import COMPOSITE_TYPES, DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, PART_VARIANTS, Rom, bgr555_rgb, decode_tile

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [("p0", "目（推測）"), ("p1", "鼻（推測）"), ("p2", "口（推測）"), ("p3", "頭（推測）"), ("p4", "肩（推測）")]


def part_image(rom: Rom, t: int, p: int, v: int) -> bytes:
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell, raw in rom.composite_part(t, p, v):
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for i, c in enumerate(decode_tile(raw)):
            out[(cy + i // 8) * w + cx + i % 8] = c
    return bytes(out)


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for t in range(COMPOSITE_TYPES):
        parts = {sid: {"items": [add(part_image(rom, t, p, v), 0) for v in range(PART_VARIANTS[p])]}
                 for p, (sid, _) in enumerate(SLOTS)}
        variants.append({"id": str(t), "label": f"型 {t}", "parts": parts})

    portraits = [{"img": add(bytes(rom.face_pixels(n)), 1), "label": f"P{n:03d}"} for n in range(1, FACE_COUNT + 1)]

    characters = []
    for p in rom.persons():
        face = p["face"]
        ch = {"id": p["id"], "name": p["name"], "reading": kaodata.hiragana(p["reading"])}
        if face & 0x8000:
            ch["face"] = {"variant": rom.composite_type(face), "parts": rom.composite_variants(face),
                          "code": f"{face:04X}"}
        else:
            ch["face"] = {"portrait": (face if 1 <= face <= FACE_COUNT else 1) - 1}
        characters.append(ch)

    meta = {
        "format": kaodata.FORMAT,
        "id": "san3-sfc",
        "game": "SAN3",
        "platform": "SFC",
        "title": {"ja": "三國志III", "zh": "三國志III"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像調色盤（全員共用）",
                      "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in map(bgr555_rgb, rom.face_palette())]}],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 san3-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Sangokushi III (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"san3-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
