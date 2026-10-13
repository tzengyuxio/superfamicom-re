#!/usr/bin/env python3
"""Export SFC 三國志IV as a kaodata dataset (san4-sfc, format kaodata/1).

Pixels are `palette * 16 + colour`: the dataset palette is the game's 2 face palettes (32 colours).
Composed faces ($C3:5303): one variant per pack (16), all with palette 0. The game's build order becomes
the slots: top face, bottom face, eyes, mouth; each slot writes whole 8x8 cells of the 40x48 face. Top and
bottom take one of the pack's 4 whole faces, eyes one of its 6 streams, mouth one of the 4 faces; every item
is a 40x48 canvas with 255 outside the slot's cells. Portraits 0-338 use the palette the game looks up per
code ($C3:598B).

Usage: .venv/bin/python san4/export_kaodata.py --out <dir> [--rom ROM]
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
    FACE_H,
    FACE_PALETTES,
    FACE_W,
    PACK_COUNT,
    PACK_CUT,
    PACK_EYES,
    PACK_MOUTH,
    PORTRAIT_COUNT,
    Rom,
    bgr555_rgb,
    decode_tile,
    le16,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
# slot id, label, code shift, code mask, streams of the pack it can take
SLOTS = [("top", "上半", 4, 3, 4), ("bottom", "下半", 6, 3, 4), ("eyes", "眼", 8, 7, 6), ("mouth", "口", 11, 3, 4)]


def tiles(start: int, length: int) -> list[int]:
    return list(range(start // 32, (start + length) // 32))


def pack_cells(rom: Rom, pack: int) -> dict[str, list[int]]:
    """Tile cells (0-29, row-major) each slot of a pack writes, as $C3:5303 copies them (byte ranges / 32)."""
    cut = le16(rom.data, PACK_CUT + 2 * pack)
    eo, mo = le16(rom.data, PACK_EYES + 2 * pack), le16(rom.data, PACK_MOUTH + 2 * pack)
    eyes = tiles(eo, 0x40 if pack in (0, 2, 8, 13) else 0x20 if pack == 4 else 0x60)
    if pack == 4:
        eyes += tiles(0x180, 0x60)
    mouth = tiles(mo, 0x60 if pack in (7, 10, 11, 14, 15) else 0x40)
    if pack in (1, 9, 10, 14, 15):
        mouth += tiles(0x2A0 if pack == 10 else 0x240 if pack == 14 else 0x220, 0x60 if pack == 10 else 0x20)
    return {"top": tiles(0, cut), "bottom": tiles(cut, 0x3C0 - cut), "eyes": eyes, "mouth": mouth}


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
    for pack in range(PACK_COUNT):
        cells = pack_cells(rom, pack)
        parts = {sid: {"items": [add(cells_image(rom.pack_part(pack, k), cells[sid], 0)) for k in range(n)]}
                 for sid, _, _, _, n in SLOTS}
        variants.append({"id": str(pack), "label": f"第 {pack} 包", "parts": parts})

    portraits = []
    for code in range(PORTRAIT_COUNT):
        pal = rom.face_palette_number(code)
        portraits.append({"img": add(bytes(pal * 16 + v for v in rom.face_pixels(code)), blob=1),
                          "label": f"{code:03d}"})

    characters = []
    for p in rom.persons():
        code = p["face"]
        ch = {"id": p["id"], "name": p["name"], "reading": kaodata.hiragana(p["reading"])}
        if code & 0x8000:
            ch["face"] = {"variant": code & 15, "parts": [code >> shift & mask for _, _, shift, mask, _ in SLOTS],
                          "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for n in range(2)
              for r, g, b in (bgr555_rgb(le16(rom.data, FACE_PALETTES + 32 * n + 2 * i)) for i in range(16))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "san4-sfc",
        "game": "SAN4",
        "platform": "SFC",
        "title": {"ja": "三國志IV", "zh": "三國志IV"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 2 組調色盤（色號＝組 × 16 ＋ 色）", "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _, _, _ in SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 san4-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Sangokushi IV (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"san4-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
