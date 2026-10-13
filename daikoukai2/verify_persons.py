#!/usr/bin/env python3
"""Check rom.Rom.persons against the game's 人物情報 screen (needs Mesen 2, about 3 minutes).

Plays as ジョアン up to free walking in Lisbon (tools/replay.py), takes a savestate, then for every person 0-119
copies the person's 50-byte record over ジョアン's (W25FC) and opens 艦隊情報 > 人物情報. The screen is built on
BG3 (tilemap at VRAM word 0x7C00): small digits are tiles 0x200 + d, big digits tiles 0x1C + 2 d (top half;
bottom half + 1), kana are tiles of an 8 x 16 font. Checked per person:
- the 7 stats (+28..+34), age (+42), 航海 / 戦闘 level (+36, +37) and experience (+38, +40) read back from the
  digit tiles;
- the face (+26): OBJ tiles at VRAM 0x3800 and CGRAM palette 10 must equal rom.Rom.face_tiles / face_palette;
- name and nationality: the kana tiles of the name (row 6) and of 国籍 (row 9) are mapped to the characters of the
  decoded name and of COUNTRIES[+49 & 15]; the mapping must be one tile per character for all persons together.
  Country 6 (海賊) is drawn as two 16 x 16 kanji instead: their BG3 tiles must equal the font glyphs of 海 and 賊.

Usage: .venv/bin/python daikoukai2/verify_persons.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
import replay
from rom import COUNTRIES, DEFAULT_ROM, FACE_BYTES, FONT, PERSON_COUNT, PERSONS, Rom, wram

OPEN_INFO = "w5 x:10 w40 right+a:10 w80 a:10 w100"
BG3 = 0x7C00 * 2
BG3_CHR = 0x6000 * 2
FACE_VRAM, FACE_CGRAM = 0x3800, 2 * 160
# (row, first column, columns) of each number on BG3; big = two-row digits
PIRATES = 6
STAT_CELLS = [(13, 20), (16, 20), (19, 20), (22, 20), (13, 27), (16, 27), (19, 27)]


def tile(vram: bytes, row: int, col: int) -> int:
    i = BG3 + 2 * (32 * row + col)
    return (vram[i] | vram[i + 1] << 8) & 0x3FF


def small_number(vram: bytes, row: int, col: int) -> int | None:
    digits = ""
    while col < 32 and 0x200 <= tile(vram, row, col) <= 0x209:
        digits += str(tile(vram, row, col) - 0x200)
        col += 1
    return int(digits) if digits else None


def big_number(vram: bytes, row: int, col: int, width: int) -> int | None:
    digits = ""
    for c in range(col, col + width):
        t = tile(vram, row, c)
        if 0x1C <= t <= 0x2E and t % 2 == 0:
            digits += str((t - 0x1C) // 2)
    return int(digits) if digits else None


def kana_tiles(vram: bytes, row: int, col: int) -> list[int]:
    out = []
    while col < 32 and tile(vram, row, col) not in (0, 0x200):
        out.append(tile(vram, row, col))
        col += 1
    return out


def glyph_on_screen(vram: bytes, t: int) -> bytes:
    """16 x 16 1bpp glyph (font layout: 8 rows of TL, TR, BL, BR) drawn with BG3 2bpp tiles t..t+3."""
    out = bytearray(32)
    for q in range(4):
        raw = vram[BG3_CHR + 16 * (t + q):BG3_CHR + 16 * (t + q) + 16]
        for y in range(8):
            out[8 * q + y] = raw[2 * y] | raw[2 * y + 1]
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證人物表（人物情報畫面）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 8th person")
    args = ap.parse_args()
    rom = Rom(args.rom)
    persons = rom.persons()
    countries = rom.string_table(COUNTRIES)
    ids = list(range(PERSON_COUNT))[::8 if args.quick else 1]
    slot = 0x7E0000 | wram(PERSONS)
    rounds = [([(slot, persons[k]["raw"])], OPEN_INFO) for k in ids]
    bad = {"stats": [], "age": [], "levels": [], "face": [], "kanji": []}
    char_tile: dict[str, set] = {}
    tile_char: dict[int, set] = {}
    for k, mem in zip(ids, replay.run(args.rom, replay.BOOT_TOWN, rounds)):
        p, vram = persons[k], mem["vram"]
        if [small_number(vram, r, c) for r, c in STAT_CELLS] != p["stats"]:
            bad["stats"].append(k)
        if big_number(vram, 9, 11, 3) != p["age"]:
            bad["age"].append(k)
        got = (big_number(vram, 12, 7, 3), small_number(vram, 13, 11), big_number(vram, 15, 7, 3),
               small_number(vram, 16, 11))
        if got != (p["sail_level"], p["sail_exp"], p["battle_level"], p["battle_exp"]):
            bad["levels"].append(k)
        if (vram[FACE_VRAM:FACE_VRAM + FACE_BYTES], mem["cgram"][FACE_CGRAM:FACE_CGRAM + 32]) != \
                (rom.face_tiles(p["face"]), rom.face_palette(p["face"])):
            bad["face"].append(k)
        texts = [(p["name"], kana_tiles(vram, 6, 11))]
        if p["country"] == PIRATES:  # 海賊 is drawn with two 16 x 16 kanji (BG3 tiles 4 per glyph)
            t = tile(vram, 9, 23)
            shown = [glyph_on_screen(vram, t), glyph_on_screen(vram, t + 4)]
            if shown != [rom.data[FONT + 32 * rom.charset.index(c):][:32] for c in countries[PIRATES]]:
                bad["kanji"].append(k)
        else:
            texts.append((countries[p["country"]], kana_tiles(vram, 9, 23)))
        for text, tiles in texts:
            for ch, t in zip(text, tiles):
                char_tile.setdefault(ch, set()).add(t)
                tile_char.setdefault(t, set()).add(ch)
            if len(text) != len(tiles):
                char_tile.setdefault(f"<len {k}: {text}>", set()).update({-1, -2})
    errors = 0
    labels = {"stats": "7 能力值 (+28..+34)", "age": "年齡 (+42)", "levels": "航海/戰鬥等級與經驗 (+36..+41)",
              "face": "頭像 tiles 與調色盤 (+26)", "kanji": "國籍 6 = 海賊 (畫面上的漢字字形)"}
    pirates = sum(persons[k]["country"] == PIRATES for k in ids)
    for key, label in labels.items():
        n = pirates if key == "kanji" else len(ids)
        errors += len(bad[key])
        print(f"[{key}] {n - len(bad[key])}/{n} {label} match the screen"
              + (f" (NG {bad[key][:20]})" if bad[key] else ""))
    clash = {c: t for c, t in char_tile.items() if len(t) > 1}
    clash.update({f"tile {t:#x}": c for t, c in tile_char.items() if len(c) > 1})
    print(f"[text] names + 国籍: {len(char_tile)} characters <-> {len(tile_char)} kana tiles, "
          + ("one to one" if not clash else f"NG {dict(list(clash.items())[:10])}"))
    errors += len(clash)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
