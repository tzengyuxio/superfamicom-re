#!/usr/bin/env python3
"""Export SFC スーパー三國志 as a kaodata dataset (san1-sfc, format kaodata/1).

Pixels are colour numbers of the one face palette (16 colours, OBJ palette 1 at ROM 0x4E711).
Composite faces ($C1:143F): one variant per male composite type (6). The game's build order becomes the slots:
part k (0-4) of the type writes its LZ stream as consecutive 8x8 cells of the 40x48 face from a per-type
position; every item is a 40x48 canvas with 255 outside the cells it writes. A character's face is
{variant: type, parts: [part variant 0-4], code: face code (4 hex digits)}.
Portraits 0-127 are the 128 portrait LZ entries (code 0000-007F). The 52 female composite faces (0x0FF-0x132) are
used by no person; they are added as rendered portraits 128-179 with their code and group 女性 (what the game
uses them for is unsolved; presumably daughters).
Characters are persons 1-255 (person 0, a second 曹操 entry the game does not list, is left out). Names are
the ROM's, except two where the game draws a look-alike glyph (NAME_FIXES, as the FC dataset writes them).

Usage: .venv/bin/python sangokushi/export_kaodata.py --out <dir> [--rom ROM]
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
    COMPOSITES,
    DEFAULT_ROM,
    FACE_H,
    FACE_SLOTS,
    FACE_W,
    LAST_FACE,
    PORTRAIT_COUNT,
    Rom,
    bgr555_rgb,
    decode_tile,
    face_kind,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
SLOTS = [("upper", "上半（推測：頭）"), ("lower", "下半（推測：肩）"), ("eyes", "眼（推測）"), ("nose", "鼻（推測）"),
         ("mouth", "口（推測）")]
assert len(SLOTS) == FACE_SLOTS
# the game's glyph (look-alike) -> the name as the FC dataset (san1-fc) writes it
NAME_FIXES = {"郭氾": "郭汜", "粱剛": "梁剛"}


def tiles_image(offset: int, raw: bytes) -> bytes:
    """40x48 image of the tiles `raw` written from byte `offset` of the 960-byte face, other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for i in range(len(raw) // 32):
        cell = offset // 32 + i
        if cell >= FACE_W * FACE_H:
            break
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for j, v in enumerate(decode_tile(raw[32 * i:32 * i + 32])):
            out[(cy + j // 8) * w + cx + j % 8] = v
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

    counts = rom.composite_slots("male")
    variants = []
    for t in range(COMPOSITES["male"][6]):
        parts = {sid: {"items": [add(tiles_image(*rom.composite_part("male", t, k, v))) for v in range(counts[k])]}
                 for k, (sid, _) in enumerate(SLOTS)}
        variants.append({"id": str(t), "label": f"男性 第 {t} 型", "parts": parts})

    portraits = [{"img": add(bytes(rom.face_pixels(n)), blob=1), "code": f"{n:04X}"} for n in range(PORTRAIT_COUNT)]
    portraits += [{"img": add(bytes(rom.face_pixels(code)), blob=1), "code": f"{code:04X}", "group": "女性"}
                  for code in range(COMPOSITES["female"][0], LAST_FACE + 1)]

    characters = []
    for n in rom.names()[1:]:
        code = n["face"]
        ch = {"id": n["id"], "name": NAME_FIXES.get(n["name"], n["name"]), "reading": kaodata.hiragana(n["reading"])}
        if face_kind(code) == "portrait":
            ch["face"] = {"portrait": code}
        else:
            t, parts = rom.composite_record(code)
            ch["face"] = {"variant": t, "parts": parts, "code": f"{code:04X}"}
        characters.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (bgr555_rgb(c) for c in rom.face_palette())]
    meta = {
        "format": kaodata.FORMAT,
        "id": "san1-sfc",
        "game": "SAN1",
        "platform": "SFC",
        "title": {"ja": "スーパー三國志", "zh": "超級三國志"},
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 san1-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Super Sangokushi (Japan).zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"san1-sfc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} variants, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
