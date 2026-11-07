"""SFC スーパー麻雀大会 (KOEI) ROM decoding.

Offsets are file offsets of the headerless 512 KB LoROM image (CPU $BB:8000-$BB:FFFF = file BB * 0x8000 + addr - 0x8000).
Data streams are KOEI LZ (tools/koei_lz.py) and are addressed by inline pointers in the code, not by a pointer table.
See docs/ROM_FORMAT.md.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz
from paths import ORIGINAL
from replay import load_rom_bytes

DEFAULT_ROM = os.path.join(ORIGINAL, "Super Mahjong Taikai (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
GLYPH16 = os.path.join(HERE, "data", "glyph16.txt")
PERSONS_TSV = os.path.join(HERE, "data", "persons.tsv")

PERSON_COUNT = 21

# Faces: one stream per opponent (3-byte pointers at $01:88C8), 6368 bytes = six 40x40 faces (5x5 4bpp tiles,
# row-major, 800 bytes each) + one 56x56 image (7x7 tiles, 1568 bytes)
FACE_STREAMS = 0x88C8
FACE_W, FACE_H = 5, 5
FACE_BYTES = 800
FACE_COUNT = 6
SPECIAL_W = 7
SPECIAL_AT, SPECIAL_BYTES = 6 * 800, 1568
FACE_LABELS = ["普通", "口 1", "口 2", "笑", "泣", "驚"]   # 0-2: talking animation (mouth frames)
SPECIAL_LABEL = "怒"   # the 56x56 image: anger (shown with face code 3)
# Per-opponent face palette (0 or 1) at $01:8925; the palettes (BGR555, 16 colours) at $01:9384 and $01:93A4
FACE_PAL_SELECT = 0x8925
FACE_PALETTES = 0x9384
# Dialogue: a line's first byte picks the face drawn next to it ($01:89CD offsets from the start of the face
# stream, $01:89D7 sizes): 0 = face 0, 1 = face 3, 2 = face 4, 3 = the 56x56 image, 4 = face 5
DIALOGUE_FACE_OFFSET = 0x89CD
DIALOGUE_FACE_SIZE = 0x89D7
DIALOGUE_FACE_COUNT = 5

# Name graphics: stream 06:D29B, 21 x 384 bytes = 6 x 2 tiles (48x16, top row then bottom row), palette $01:93C4
NAME_STREAM = 0x06D29B
NAME_W, NAME_H = 6, 2
NAME_BYTES = 384
NAME_PALETTE = 0x93C4

# Playing parameters: 21 x 12 bytes at $01:8B3F, expanded by $00:ACB1 into 22 nibbles (bytes 0-10, high nibble first)
# and 8 flag bits (byte 11, MSB first)
PARAMS = 0x8B3F
PARAM_SIZE = 12

# Dialogue: per opponent one stream (LE16 address at $01:89E1, bank at $01:8A0B) of 133 lines x 17 bytes:
# face (DIALOGUE_FACE_*), then 16 font codes (2 lines of 8; FF = blank)
DIALOGUE_ADDR = 0x89E1
DIALOGUE_BANK = 0x8A0B
LINE_COUNT, LINE_SIZE = 133, 17
# Situations 0-65: first line ($01:8A20, 67 values, the last = 133), chance ($01:8A63: a line is start + random(n);
# no line when that reaches the next situation's first line), flags ($01:8AA5)
SITUATION_COUNT = 66
SITUATION_START = 0x8A20
SITUATION_CHANCE = 0x8A63
SITUATION_FLAGS = 0x8AA5

# Dialogue font: 8x16 glyphs (two 4bpp tiles, top then bottom), codes 00-10 in stream 06:E5F6 at 0xDC0,
# codes 11-D3 in stream 07:B18F; BG tile of code c = 0x6E + 2c (+1 for the bottom half)
FONT_LOW_STREAM, FONT_LOW_AT = 0x06E5F6, 0xDC0
FONT_HIGH_STREAM, FONT_HIGH_FIRST = 0x07B18F, 0x11
FONT_CODES = 0xD4

# Yaku names: 52 strings at $01:8D49 of 16x16 glyph numbers + 1, each ended by 0 (drawn by $00:C384); glyphs: stream
# 07:BBAD, 99 x 128 bytes (2 x 2 4bpp tiles: top-left, top-right, bottom-left, bottom-right); byte b is drawn with
# tiles 0x8C + 4b .. 0x8F + 4b
YAKU_NAMES = 0x8D49
YAKU_COUNT = 52
GLYPH16_STREAM = 0x07BBAD
GLYPH16_COUNT = 99


def lorom(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def decode_tile(raw: bytes) -> list[int]:
    """One 4bpp SNES tile (32 bytes) -> 64 colour numbers, row-major."""
    out = []
    for y in range(8):
        p0, p1, p2, p3 = raw[2 * y], raw[2 * y + 1], raw[16 + 2 * y], raw[17 + 2 * y]
        for x in range(7, -1, -1):
            out.append((p0 >> x & 1) | (p1 >> x & 1) << 1 | (p2 >> x & 1) << 2 | (p3 >> x & 1) << 3)
    return out


def tiles_to_pixels(tiles: bytes, w: int, h: int) -> list[int]:
    """w x h tiles stored row-major -> (8w x 8h) colour numbers, row-major."""
    out = [0] * (w * h * 64)
    for t in range(w * h):
        for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
            out[(t // w * 8 + i // 8) * w * 8 + t % w * 8 + i % 8] = v
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    """SNES colour -> 8-bit RGB (5-bit value << 3 | value >> 2, as Mesen shows it)."""
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def load_charset(path: str = CHARSET) -> dict[int, str]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip("\n"):
                continue
            code, ch = line.rstrip("\n").split("\t")
            out[int(code, 16)] = ch
    assert sorted(out) == list(range(FONT_CODES)), len(out)
    return out


def load_glyph16(path: str = GLYPH16) -> str:
    with open(path, encoding="utf-8") as f:
        out = "".join(line.rstrip("\n").split("\t")[1] for line in f if not line.startswith("#") and line.strip())
    assert len(out) == GLYPH16_COUNT, len(out)
    return out


def load_persons(path: str = PERSONS_TSV) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split("\t") for line in f if not line.startswith("#")]
    head = rows[0]
    return [dict(zip(head, r + [""] * (len(head) - len(r)))) for r in rows[1:]]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.tables = koei_lz.find_tables(self.data)
        self.charset = load_charset()
        self.glyphs16 = load_glyph16()
        self._cache: dict[int, bytes] = {}

    def stream(self, addr: int) -> bytes:
        """Decompressed LZ stream at CPU address addr."""
        if addr not in self._cache:
            self._cache[addr] = koei_lz.decompress(self.data, lorom(addr), self.tables)[0]
        return self._cache[addr]

    def long_ptr(self, at: int) -> int:
        return int.from_bytes(self.data[at:at + 3], "little")

    # --- text ---
    def text(self, codes: bytes, width: int = 8) -> str:
        """Font codes -> str, a newline every `width` codes; FF = blank (trailing blanks dropped)."""
        lines = []
        for i in range(0, len(codes), width):
            lines.append("".join(" " if c == 0xFF else self.charset.get(c, f"[{c:02X}]")
                                 for c in codes[i:i + width]).rstrip(" "))
        return "\n".join(lines).rstrip("\n")

    def glyph(self, code: int) -> bytes:
        """64 bytes: the two 4bpp tiles (top, bottom) of a font code."""
        if code < FONT_HIGH_FIRST:
            return self.stream(FONT_LOW_STREAM)[FONT_LOW_AT + 64 * code:FONT_LOW_AT + 64 * code + 64]
        o = 64 * (code - FONT_HIGH_FIRST)
        return self.stream(FONT_HIGH_STREAM)[o:o + 64]

    # --- persons ---
    def persons(self) -> list[dict]:
        names = load_persons()
        out = []
        for i in range(PERSON_COUNT):
            out.append({"id": i, "name": names[i]["名前"], "reading": names[i]["読み"], "origin": names[i]["[EXT]出典"],
                        "face_stream": self.long_ptr(FACE_STREAMS + 3 * i),
                        "palette": self.data[FACE_PAL_SELECT + i],
                        "dialogue_stream": le16(self.data, DIALOGUE_ADDR + 2 * i) | self.data[DIALOGUE_BANK + i] << 16,
                        "params": self.params(i)})
        return out

    def params(self, i: int) -> dict:
        r = self.data[PARAMS + PARAM_SIZE * i:PARAMS + PARAM_SIZE * (i + 1)]
        nibbles = [n for b in r[:11] for n in (b >> 4, b & 15)]
        flags = [r[11] >> (7 - k) & 1 for k in range(8)]
        return {"raw": r, "nibbles": nibbles, "flags": flags}

    # --- faces ---
    def face_palette(self, k: int) -> list[int]:
        return [le16(self.data, FACE_PALETTES + 32 * k + 2 * i) for i in range(16)]

    def face_stream(self, i: int) -> bytes:
        return self.stream(self.long_ptr(FACE_STREAMS + 3 * i))

    def face_tiles(self, i: int, k: int) -> bytes:
        """Tiles of opponent i's face k (0-5: 40x40; 6: the 56x56 image)."""
        s = self.face_stream(i)
        return s[SPECIAL_AT:SPECIAL_AT + SPECIAL_BYTES] if k == FACE_COUNT else s[FACE_BYTES * k:FACE_BYTES * (k + 1)]

    def face_size(self, k: int) -> tuple[int, int]:
        return (SPECIAL_W, SPECIAL_W) if k == FACE_COUNT else (FACE_W, FACE_H)

    def face_pixels(self, i: int, k: int) -> list[int]:
        w, h = self.face_size(k)
        return tiles_to_pixels(self.face_tiles(i, k), w, h)

    def face_rgb(self, i: int, k: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette(self.data[FACE_PAL_SELECT + i])]
        return [pal[v] for v in self.face_pixels(i, k)]

    def dialogue_faces(self) -> list[int]:
        """Face number (0-6) for each value 0-4 of a dialogue line's first byte."""
        out = []
        for e in range(DIALOGUE_FACE_COUNT):
            off = le16(self.data, DIALOGUE_FACE_OFFSET + 2 * e) - 0x1000
            out.append(FACE_COUNT if off == SPECIAL_AT else off // FACE_BYTES)
        return out

    # --- names ---
    def name_tiles(self, i: int) -> bytes:
        return self.stream(NAME_STREAM)[NAME_BYTES * i:NAME_BYTES * (i + 1)]

    def name_rgb(self, i: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(le16(self.data, NAME_PALETTE + 2 * c)) for c in range(16)]
        return [pal[v] for v in tiles_to_pixels(self.name_tiles(i), NAME_W, NAME_H)]

    # --- dialogue ---
    def situations(self) -> list[dict]:
        out = []
        for s in range(SITUATION_COUNT):
            first, nxt = self.data[SITUATION_START + s], self.data[SITUATION_START + s + 1]
            out.append({"id": s, "first": first, "count": nxt - first, "chance": self.data[SITUATION_CHANCE + s],
                        "flags": self.data[SITUATION_FLAGS + s]})
        return out

    def dialogue_raw(self, i: int) -> bytes:
        return self.stream(le16(self.data, DIALOGUE_ADDR + 2 * i) | self.data[DIALOGUE_BANK + i] << 16)

    def dialogue(self, i: int) -> list[dict]:
        raw = self.dialogue_raw(i)
        faces = self.dialogue_faces()
        out = []
        for n in range(LINE_COUNT):
            r = raw[LINE_SIZE * n:LINE_SIZE * (n + 1)]
            out.append({"line": n, "face_code": r[0], "face": faces[r[0]] if r[0] < len(faces) else None,
                        "codes": r[1:], "text": self.text(r[1:])})
        return out

    # --- yaku ---
    def glyph16(self, g: int) -> bytes:
        return self.stream(GLYPH16_STREAM)[128 * g:128 * (g + 1)]

    def yaku_codes(self) -> list[bytes]:
        out, i = [], YAKU_NAMES
        for _ in range(YAKU_COUNT):
            j = self.data.index(0, i)
            out.append(self.data[i:j])
            i = j + 1
        return out

    def yaku(self) -> list[dict]:
        return [{"id": n, "codes": c, "name": "".join(self.glyphs16[b - 1] for b in c)}
                for n, c in enumerate(self.yaku_codes())]
