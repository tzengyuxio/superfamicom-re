#!/usr/bin/env python3
"""Export SFC 信長の野望・天翔記 as a kaodata dataset (nobu6-sfc, format kaodata/1).

Pixels are `palette * 16 + colour`: the dataset palette is the game's 3 face palettes (48 colours).
Generic faces: one variant per pack (19), each with the pack's palette. The game's build order
($C3:2983) becomes the slots: top rows, bottom rows, eyes (3 tiles), mouth (1-3 tiles); every slot has
the pack's 4 faces as items, each a 40x48 canvas with 255 outside the slot's cells. Pack 0 takes tile
20 from the top face. Portraits 0-311 use the palette the game looks up per code.

Usage: .venv/bin/python tenshouki/export_kaodata.py --out <dir> [--rom ROM]
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
    PACK_ENTRY,
    PACK_MOUTH_TILES,
    PACK_ROWS,
    PORTRAIT_COUNT,
    Rom,
    bgr555_rgb,
    decode_tile,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [("top", "上半", 5), ("bottom", "下半", 7), ("eyes", "眼", 9), ("mouth", "口", 11)]  # id, label, code shift


def pack_cells(rom: Rom, pack: int) -> dict[str, list[int]]:
    """Tile cells (0-29, row-major) each slot of a pack writes."""
    top, eyes, mouth = rom.data[PACK_ROWS + 3 * pack:PACK_ROWS + 3 * pack + 3]
    n = rom.data[PACK_MOUTH_TILES + pack]
    cells = {"top": list(range(FACE_W * top)), "bottom": list(range(FACE_W * top, FACE_W * FACE_H)),
             "eyes": [10 + eyes + i for i in range(3)], "mouth": [20 + mouth + i for i in range(n)]}
    if pack == 0:  # $C3:2B33: tile 20 comes from the top face
        cells["top"].append(20)
        cells["bottom"].remove(20)
    return cells


def cells_image(tiles: bytes, cells: list[int], palette: int) -> bytes:
    """40x48 image of the given cells of a 960-byte face, other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for cell in cells:
        px = decode_tile(tiles[32 * cell:32 * cell + 32])
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
    for pack in range(PACK_COUNT):
        e = rom.entry(PACK_ENTRY + pack)
        pal = rom.face_palette_number(0x8000 | pack)
        cells = pack_cells(rom, pack)
        parts = {sid: {"items": [add(cells_image(e[FACE_BYTES * s:FACE_BYTES * (s + 1)], cells[sid], pal))
                                 for s in range(4)]} for sid, _, _ in SLOTS}
        variants.append({"id": str(pack), "label": f"第 {pack} 包", "parts": parts})

    portraits = []
    for code in range(PORTRAIT_COUNT):
        pal = rom.face_palette_number(code)
        portraits.append({"img": add(bytes(pal * 16 + v for v in rom.face_pixels(code)), blob=1),
                          "code": f"{code:04X}"})

    characters = []
    for p in rom.persons():
        code = p["face"]
        ch = {"id": p["id"], "name": " ".join(rom.name(p["id"]))}
        if code & 0x8000:
            ch["face"] = {"variant": code & 0x1F, "parts": [code >> shift & 3 for _, _, shift in SLOTS],
                          "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for pal in rom.face_palettes() for r, g, b in map(bgr555_rgb, pal)]
    meta = {
        "format": kaodata.FORMAT,
        "id": "nobu6-sfc",
        "game": "NOBU6",
        "platform": "SFC",
        "title": {"ja": "信長の野望・天翔記", "zh": "信長之野望・天翔記"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 3 組調色盤（色號＝組 × 16 ＋ 色）", "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _ in SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 nobu6-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Nobunaga no Yabou - Tenshouki (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"nobu6-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
