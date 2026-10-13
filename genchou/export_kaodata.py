#!/usr/bin/env python3
"""Export SFC スーパー蒼き狼と白き牝鹿・元朝秘史 as a kaodata dataset (genchou-sfc, format kaodata/1).

Pixels are `palette * 16 + colour`: the dataset palette is the game's 2 face palettes (CGRAM palettes 2 and 3,
32 colours). Composed faces ($C4:5812): one variant per head (56 = group * 7 + n, group = code bits 12-14). The game builds a face
from 5 parts of the head (eyes, nose, mouth, top, body); each part has 2 versions chosen by one bit of the face
code, and the 5 parts cover the 30 cells of the 40x48 face exactly once, so every slot has two items (40x48
canvases, 255 outside the part's cells). Heads of groups 4-6 use palette 2, the others palette 3. Portraits
0-96 (0-56 men, 57-96 women = woman face code + 57) use palette 3.

Characters: the scenario persons and the family block distinct by (name, face code) get ids 0-; the women of
the 4 scenarios distinct the same way get ids 1000-.

Usage: .venv/bin/python genchou/export_kaodata.py --out <dir> [--rom ROM]
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
    FACE_GROUPS,
    FACE_H,
    FACE_PALETTES,
    FACE_W,
    PART_NAMES,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    WOMAN_PORTRAIT,
    Rom,
    bgr555_rgb,
    decode_tile,
    le16,
)

CANVAS = (FACE_W * 8, FACE_H * 8)
HEADS = 56
SLOT_LABELS = {"eyes": "眼", "nose": "鼻", "mouth": "口", "top": "上部", "body": "下部"}
WOMEN_ID = 1000
PALETTE_NUMBERS = sorted(FACE_PALETTES)          # dataset palette k*16.. = CGRAM palette PALETTE_NUMBERS[k]


def cells_image(tiles: bytes, first: int, cells: list[int], pal: int) -> bytes:
    """40x48 image: source tile first + i of the head drawn at face cell cells[i], other cells transparent."""
    w, h = CANVAS
    out = bytearray([kaodata.TRANSPARENT]) * (w * h)
    for i, cell in enumerate(cells):
        px = decode_tile(tiles[32 * (first + i):32 * (first + i) + 32])
        cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
        for j, v in enumerate(px):
            out[(cy + j // 8) * w + cx + j % 8] = pal * 16 + v
    return bytes(out)


def reading(name: str) -> str | None:
    """Kana-only names -> hiragana ('・' becomes a space); names with kanji have none."""
    s = kaodata.hiragana(name).replace("・", " ")
    return s if all("ぁ" <= c <= "ゖ" or c in "ー " for c in s) else None


def characters(rom: Rom) -> list[dict]:
    out = []
    for base, rows, woman in (
            (0, [p for s in range(SCENARIO_COUNT) for p in rom.persons(s)] + rom.family(), False),
            (WOMEN_ID, [w for s in range(SCENARIO_COUNT) for w in rom.women(s)], True)):
        seen = []
        for r in rows:
            if (key := (r["name"], r["face"])) not in seen:
                seen.append(key)
                out.append({"id": base + len(seen) - 1, "name": r["name"], "code": r["face"], "woman": woman})
    return out


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
    for head in range(HEADS):
        culture = head // 7
        pal = PALETTE_NUMBERS.index(rom.face_palette_number(0x8000 | culture << 12))
        tiles = rom.head_tiles(head)
        parts = {}
        for name, part in zip(PART_NAMES, rom.head_parts(head)):
            parts[name] = {"items": [add(cells_image(tiles, part["tile"] + v * part["count"], part["cells"], pal))
                                     for v in range(2)]}
        variants.append({"id": str(head), "label": f"{FACE_GROUPS[culture]}(推測) {head % 7}", "parts": parts})

    portraits = []
    for n in range(PORTRAIT_COUNT):
        pal = PALETTE_NUMBERS.index(rom.face_palette_number(n))
        portraits.append({"img": add(bytes(pal * 16 + v for v in rom.face_pixels(n)), blob=1),
                          "label": f"{n:02d}" if n < WOMAN_PORTRAIT else f"女 {n - WOMAN_PORTRAIT:02d}"})

    chars = []
    for c in characters(rom):
        ch = {"id": c["id"], "name": c["name"]}
        if (r := reading(c["name"])) is not None:
            ch["reading"] = r
        code = c["code"]
        if code & 0x8000:
            f = rom.face_fields(code)
            ch["face"] = {"variant": f["head"], "parts": f["variants"], "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code + (WOMAN_PORTRAIT if c["woman"] else 0)}
        chars.append(ch)

    colors = [f"#{r:02x}{g:02x}{b:02x}" for p in PALETTE_NUMBERS
              for r, g, b in (bgr555_rgb(le16(rom.data, FACE_PALETTES[p] + 2 * i)) for i in range(16))]
    meta = {
        "format": kaodata.FORMAT,
        "id": "genchou-sfc",
        "game": "GENCHOU",
        "platform": "SFC",
        "title": {"ja": "スーパー蒼き狼と白き牝鹿・元朝秘史", "zh": "蒼狼與白鹿・元朝秘史（SFC）"},
        "source": {"producer": "superfamicom-re", "revision": kaodata.revision(REPO),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "face", "label": "頭像 2 組調色盤（色號＝組 × 16 ＋ 色；組 0 = CGRAM 2、組 1 = CGRAM 3）",
                      "colors": colors}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": name, "label": SLOT_LABELS[name]} for name in PART_NAMES],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": chars,
    }
    return meta, [bytes(b) for b in blobs]


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 genchou-sfc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/ 的 zip 或 .sfc")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    kaodata.write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    women = [c for c in chars if c["id"] >= WOMEN_ID]
    print(f"genchou-sfc: {len(chars)} characters ({len(chars) - len(women)} men, {len(women)} women; "
          f"{len(chars) - len(mobs)} portrait, {len(mobs)} composite), {len(meta['composite']['variants'])} "
          f"variants, {len(meta['portraits'])} portraits, {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
